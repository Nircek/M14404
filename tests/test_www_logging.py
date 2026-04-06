import json
from typing import Optional

from M14404.subdomains.www import (
    _split_headers,
    _build_common_payload,
    _get_client_ip_from_scope,
    _get_full_url_from_request,
    _get_full_url_from_websocket,
)


class MockRequest:
    """Minimal stand-in for :class:`starlette.requests.Request`."""

    def __init__(
        self,
        headers: Optional[dict[str, str]] = None,
        url_path: str = "/",
        url_query: str = "",
        method: str = "GET",
    ) -> None:
        self.headers = headers or {}
        self.url = type("URL", (), {"path": url_path, "query": url_query})
        self.method = method


class MockWebSocket:
    """Minimal stand-in for :class:`starlette.websockets.WebSocket`."""

    def __init__(
        self,
        headers: Optional[dict[str, str]] = None,
        url_path: str = "/",
        url_query: str = "",
    ) -> None:
        self.headers = headers or {}
        self.url = type("URL", (), {"path": url_path, "query": url_query})


def test_split_headers() -> None:
    headers = {
        "user-agent": "test-agent",
        "accept": "application/json",
        "x-custom": "value1",
        "content-type": "text/plain",
    }
    user_agent, accept, other_json = _split_headers(headers)
    assert user_agent == "test-agent"
    assert accept == "application/json"

    other_dict = json.loads(other_json)
    assert other_dict == {"x-custom": "value1", "content-type": "text/plain"}


def test_split_headers_missing() -> None:
    headers = {"x-custom": "value1"}
    user_agent, accept, other_json = _split_headers(headers)
    assert user_agent is None
    assert accept is None

    other_dict = json.loads(other_json)
    assert other_dict == {"x-custom": "value1"}


def test_build_common_payload() -> None:
    headers = {
        "user-agent": "test-agent",
        "accept": "application/json",
        "x-custom": "value1",
    }
    payload = _build_common_payload(
        client_ip="192.168.1.1",
        method="GET",
        full_url="http://abc.xyz/path",
        headers=headers,
    )
    assert payload.client_ip == "192.168.1.1"
    assert payload.http_method == "GET"
    assert payload.full_url == "http://abc.xyz/path"
    assert payload.user_agent == "test-agent"
    assert payload.accept == "application/json"
    assert json.loads(payload.other_headers) == {"x-custom": "value1"}
    assert payload.datetime.endswith("+00:00")  # timezone-aware ISO format


def test_get_client_ip_from_scope() -> None:
    assert _get_client_ip_from_scope({"client": ("127.0.0.1", 12345)}) == "127.0.0.1"
    assert _get_client_ip_from_scope({"client": ["192.168.0.1", 80]}) == "192.168.0.1"
    assert _get_client_ip_from_scope({"client": None}) == ""
    assert _get_client_ip_from_scope({}) == ""


def test_url_extraction_request() -> None:
    req1 = MockRequest(headers={"host": "abc.xyz"}, url_path="/test", url_query="q=1")
    assert _get_full_url_from_request(req1) == "abc.xyz/test?q=1"  # type: ignore[arg-type]

    req2 = MockRequest(headers={"host": "abc.xyz"}, url_path="/test", url_query="")
    assert _get_full_url_from_request(req2) == "abc.xyz/test"  # type: ignore[arg-type]

    req3 = MockRequest(headers={}, url_path="/test", url_query="q=1")
    assert _get_full_url_from_request(req3) == "/test?q=1"  # type: ignore[arg-type]


def test_url_extraction_websocket() -> None:
    ws1 = MockWebSocket(headers={"host": "abc.xyz"}, url_path="/ws", url_query="q=1")
    assert _get_full_url_from_websocket(ws1) == "abc.xyz/ws?q=1"  # type: ignore[arg-type]

    ws2 = MockWebSocket(headers={"host": "abc.xyz"}, url_path="/ws", url_query="")
    assert _get_full_url_from_websocket(ws2) == "abc.xyz/ws"  # type: ignore[arg-type]

    ws3 = MockWebSocket(headers={}, url_path="/ws", url_query="q=1")
    assert _get_full_url_from_websocket(ws3) == "/ws?q=1"  # type: ignore[arg-type]
