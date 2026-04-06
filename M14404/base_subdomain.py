from typing import Any, ClassVar

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.websockets import WebSocket


class BaseSubdomainHandler:
    subdomain_key: ClassVar[str]

    def __init__(self, *, origin_domain_name: str) -> None:
        self.origin_domain_name = origin_domain_name

    async def handle_http(self, request: Request) -> Response:
        return PlainTextResponse("method not allowed", status_code=405)

    async def handle_ws(self, websocket: WebSocket) -> Any:
        await websocket.close(code=1008)
        return None
