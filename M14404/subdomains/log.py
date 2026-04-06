import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, Mapping, Optional, Tuple

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket, WebSocketDisconnect
from tortoise import fields, models
from tortoise.context import TortoiseContext, get_current_context

from .. import db
from ..base_subdomain import BaseSubdomainHandler


class HTTPLog(models.Model):
    id = fields.IntField(primary_key=True)
    client_ip = fields.CharField(max_length=64, null=True)
    datetime = fields.DatetimeField()
    http_method = fields.CharField(max_length=16)
    full_url = fields.TextField()
    user_agent = fields.TextField(null=True)
    accept = fields.TextField(null=True)
    other_headers: fields.JSONField[dict[str, str]] = fields.JSONField()

    class Meta:
        table = "http_logs"


class WSLog(models.Model):
    id = fields.IntField(primary_key=True)
    client_ip = fields.CharField(max_length=64, null=True)
    datetime = fields.DatetimeField()
    http_method = fields.CharField(max_length=32)
    full_url = fields.TextField()
    user_agent = fields.TextField(null=True)
    accept = fields.TextField(null=True)
    other_headers: fields.JSONField[dict[str, str]] = fields.JSONField()

    class Meta:
        table = "ws_logs"


@dataclasses.dataclass
class LogPayload:
    client_ip: str
    datetime: str
    http_method: str
    full_url: str
    user_agent: Optional[str]
    accept: Optional[str]
    other_headers: str


def _split_headers(
    headers: Mapping[str, str],
) -> Tuple[Optional[str], Optional[str], str]:
    """Extract ``user-agent`` and ``accept`` from *headers*, returning remaining headers as JSON.

    Returns:
        A 3-tuple of ``(user_agent, accept, other_headers_json)``.
    """
    user_agent = headers.get("user-agent")
    accept = headers.get("accept")

    other: Dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in {"user-agent", "accept"}:
            continue
        other[key] = value

    return user_agent, accept, json.dumps(other, ensure_ascii=False)


def _build_common_payload(
    *,
    client_ip: str,
    method: str,
    full_url: str,
    headers: Mapping[str, str],
) -> LogPayload:
    """Build a :class:`LogPayload` from the common fields shared by HTTP and WS logs."""
    user_agent, accept, other_json = _split_headers(headers)
    now_iso = datetime.now(timezone.utc).isoformat()
    return LogPayload(
        client_ip=client_ip,
        datetime=now_iso,
        http_method=method,
        full_url=full_url,
        user_agent=user_agent,
        accept=accept,
        other_headers=other_json,
    )


def _get_client_ip_from_scope(scope: Mapping[str, Any]) -> str:
    """Return the client IP address from an ASGI *scope*, or an empty string if unavailable."""
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and client:
        return str(client[0])
    return ""


def _get_full_url_from_request(request: Request) -> str:
    """Construct a host-prefixed URL string from a Starlette :class:`~starlette.requests.Request`."""
    host = request.headers.get("host", "")
    url = request.url
    path_and_query = url.path
    if url.query:
        path_and_query += f"?{url.query}"
    if host:
        return f"{host}{path_and_query}"
    return str(path_and_query)


def _get_full_url_from_websocket(websocket: WebSocket) -> str:
    """Construct a host-prefixed URL string from a Starlette :class:`~starlette.websockets.WebSocket`."""
    host = websocket.headers.get("host", "")
    url = websocket.url
    path_and_query = url.path
    if url.query:
        path_and_query += f"?{url.query}"
    if host:
        return f"{host}{path_and_query}"
    return str(path_and_query)


def _normalise_headers(raw_headers: Any) -> Dict[str, str]:
    """Decode a sequence of raw ``(name, value)`` header pairs into a lowercase-keyed dict."""
    return {
        (k.decode().lower() if isinstance(k, bytes) else k.lower()): (
            v.decode() if isinstance(v, bytes) else v
        )
        for k, v in raw_headers
    }


async def _insert_http_log(payload: LogPayload) -> int:
    """Persist *payload* as an :class:`HTTPLog` row and return the new row ID."""
    await db.ensure_db_ready()
    if get_current_context() is None:
        async with TortoiseContext():
            return await _insert_http_log(payload)

    created = await HTTPLog.create(
        client_ip=payload.client_ip,
        datetime=datetime.fromisoformat(payload.datetime),
        http_method=payload.http_method,
        full_url=payload.full_url,
        user_agent=payload.user_agent,
        accept=payload.accept,
        other_headers=payload.other_headers,
    )
    return created.id


async def _insert_ws_log(payload: LogPayload) -> int:
    """Persist *payload* as a :class:`WSLog` row and return the new row ID."""
    await db.ensure_db_ready()
    if get_current_context() is None:
        async with TortoiseContext():
            return await _insert_ws_log(payload)

    created = await WSLog.create(
        client_ip=payload.client_ip,
        datetime=datetime.fromisoformat(payload.datetime),
        http_method=payload.http_method,
        full_url=payload.full_url,
        user_agent=payload.user_agent,
        accept=payload.accept,
        other_headers=payload.other_headers,
    )
    return created.id


class LogSubdomainHandler(BaseSubdomainHandler):
    subdomain_key: ClassVar[str] = "log"

    _html_template: ClassVar[Optional[str]] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if LogSubdomainHandler._html_template is None:
            template_path = Path(__file__).parent / "log.html"
            LogSubdomainHandler._html_template = template_path.read_text("utf-8")

    async def handle_http(self, request: Request) -> HTMLResponse:
        client_ip = _get_client_ip_from_scope(request.scope)
        full_url = _get_full_url_from_request(request)
        headers = _normalise_headers(request.headers.raw)
        payload = _build_common_payload(
            client_ip=client_ip,
            method=request.method,
            full_url=full_url,
            headers=headers,
        )
        inserted_id = await _insert_http_log(payload)
        html = self._html_template.replace("{inserted_id}", str(inserted_id))  # type: ignore[union-attr]
        return HTMLResponse(html)

    async def handle_ws(self, websocket: WebSocket) -> Any:
        client_ip = _get_client_ip_from_scope(websocket.scope)
        full_url = _get_full_url_from_websocket(websocket)
        headers = _normalise_headers(websocket.headers.raw)

        payload = _build_common_payload(
            client_ip=client_ip,
            method="WS_HANDSHAKE",
            full_url=full_url,
            headers=headers,
        )
        handshake_id = await _insert_ws_log(payload)
        await websocket.accept()
        await websocket.send_text(str(handshake_id))

        try:
            while True:
                _ = await websocket.receive_text()
                msg_payload = _build_common_payload(
                    client_ip=client_ip,
                    method="WS_MESSAGE",
                    full_url=full_url,
                    headers=headers,
                )
                next_id = await _insert_ws_log(msg_payload)
                await websocket.send_text(str(next_id))
        except WebSocketDisconnect:
            return None
        except Exception:
            await websocket.close(code=1011)
            return None
