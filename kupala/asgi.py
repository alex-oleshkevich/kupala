from __future__ import annotations

import typing
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.middleware import MiddlewareStack
from kupala.middleware.errors import ServerErrorMiddleware
from kupala.middleware.exception import ErrorHandler, ExceptionMiddleware
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Router, Routes


class ASGIHandler:
    def __init__(
        self,
        *,
        debug: bool,
        routes: Routes,
        middleware: MiddlewareStack,
        error_handlers: dict[typing.Type[Exception] | int, typing.Optional[ErrorHandler]],
        exception_handler: typing.Callable[[Request, Exception], Response] | None,
    ) -> None:
        self.debug = debug
        self.middleware = middleware
        self.routes = Routes(routes or [])
        self.error_handlers = error_handlers
        self.exception_handler = exception_handler

        middleware.use(ExceptionMiddleware, handlers=error_handlers)
        middleware.top(ServerErrorMiddleware, debug=debug, handler=self.exception_handler)
        self.router = Router(routes=routes)
        self.asgi_app: ASGIApp = self.router
        for mw in reversed(middleware):
            self.asgi_app = mw.wrap(self.asgi_app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope['type'] in {'http', 'websocket', 'lifespan'}
        await self.asgi_app(scope, receive, send)
