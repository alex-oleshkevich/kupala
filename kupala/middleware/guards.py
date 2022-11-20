import typing
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.guards import Guard, call_guards
from kupala.requests import Request


class GuardsMiddleware:
    def __init__(self, app: ASGIApp, guards: typing.Iterable[Guard]) -> None:
        self.app = app
        self.guards = guards

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        if response := await call_guards(request, self.guards):
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
