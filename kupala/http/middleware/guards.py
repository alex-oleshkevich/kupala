import typing
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import Request
from kupala.http.guards import Guard, call_guards


class GuardsMiddleware:
    def __init__(self, app: ASGIApp, guards: typing.Iterable[Guard]) -> None:
        self.app = app
        self.guards = guards

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        await call_guards(request, self.guards)
        await self.app(scope, receive, send)
