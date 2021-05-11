import typing as t

from starlette.middleware import base
from starlette.types import Receive, Scope, Send

from kupala.requests import Request
from kupala.responses import Response

RequestResponseEndpoint = t.Callable[[Request], t.Awaitable[Response]]


class BaseHTTPMiddleware(base.BaseHTTPMiddleware):
    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response = await self.dispatch_func(scope["request"], self.call_next)
        await response(scope, receive, send)

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        raise NotImplementedError()  # pragma: no cover
