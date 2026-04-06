from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..base_subdomain import BaseSubdomainHandler


class RootSubdomainHandler(BaseSubdomainHandler):
    subdomain_key = "_"

    async def handle_http(self, request: Request) -> RedirectResponse:
        location = f"{request.url.scheme}://www.{request.url.netloc}{request.url.path}"
        if request.url.query:
            location += f"?{request.url.query}"
        return RedirectResponse(url=location, status_code=308)
