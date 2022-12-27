import anyio
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class TimeoutMiddleware:
    def __init__(self, app: ASGIApp, timeout: float = 30) -> None:
        self.app = app
        self.timeout = timeout

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            with anyio.fail_after(self.timeout):
                await self.app(scope, receive, send)
        except TimeoutError:
            response = PlainTextResponse("Gateway Timeout", status_code=504)
            await response(scope, receive, send)
