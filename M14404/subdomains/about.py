from typing import Any

from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.websockets import WebSocket

from ..base_subdomain import BaseSubdomainHandler


class AboutSubdomainHandler(BaseSubdomainHandler):
    subdomain_key = "about"

    async def handle_http(self, request: Request) -> PlainTextResponse:
        return PlainTextResponse("M14404", status_code=200)

    async def handle_ws(self, websocket: WebSocket) -> Any:
        await websocket.accept()
        await websocket.send_text("M14404")
        await websocket.close(code=1000)
        return None
