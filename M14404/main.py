"""ASGI application entry point.

Creates and configures the :class:`~starlette.applications.Starlette` app,
wires up the two catch-all routes (HTTP and WebSocket), and wraps everything
in Uvicorn's :class:`~uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware`
so that client IPs are correctly extracted behind a reverse proxy.

Usage (with uvicorn)::

    uvicorn M14404.main:app
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from . import db
from . import resolver_service
from .settings import load_settings


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """Open and close the database connection around the application lifetime."""
    settings = load_settings()
    app.state.settings = settings
    await db.init_db(settings.database_path)
    try:
        yield
    finally:
        await db.close_db()


async def catch_all_http(request: Request) -> Response:
    settings = request.app.state.settings
    host = request.headers.get("host", "")
    origin_domain_name = settings.origin_domain_name
    handler = resolver_service.resolve_handler(
        host=host,
        origin_domain_name=origin_domain_name,
    )
    if not handler:
        return PlainTextResponse(f"`{host}` not found", status_code=404)
    return await handler.handle_http(request)


async def catch_all_ws(websocket: WebSocket) -> None:
    settings = websocket.app.state.settings
    origin_domain_name = settings.origin_domain_name
    handler = resolver_service.resolve_handler(
        host=websocket.headers.get("host", ""),
        origin_domain_name=origin_domain_name,
    )
    if not handler:
        await websocket.close(code=1008)
        return
    await handler.handle_ws(websocket)


routes = [
    Route(
        "/{path:path}",
        endpoint=catch_all_http,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    ),
    WebSocketRoute("/{path:path}", endpoint=catch_all_ws),
]


def create_app() -> Starlette:
    M14404 = Starlette(
        debug=load_settings().debug,
        routes=routes,
        lifespan=lifespan,
    )
    return M14404


M14404 = create_app()
app = ProxyHeadersMiddleware(M14404, trusted_hosts="*")  # type: ignore[arg-type]
