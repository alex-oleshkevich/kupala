import anyio
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.responses import PlainTextResponse


class TimeoutMiddleware:
    def __init__(self, app: ASGIApp, timeout: int = 30) -> None:
        self.app = app
        self.timeout = timeout

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            async with anyio.fail_after(self.timeout):
                await self.app(scope, receive, send)
        except TimeoutError:
            response = PlainTextResponse('Gateway Timeout', 504)
            await response(scope, receive, send)
