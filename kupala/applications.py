import contextlib
import typing

import click
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.routing import Router
from starlette.types import Receive, Scope, Send

from kupala.dependencies import (
    INVOCATION_CONTEXT_KEY,
    InjectionScope,
    InvocationContext,
)
from kupala.error_handlers import (
    ErrorHandler,
    http_error_handler,
    server_error_handler,
    websocket_error_handler,
)
from kupala.errors import BaseHTTPError
from kupala.middleware import Middleware, WebSocketMiddleware
from kupala.routing import Routes
from kupala.websockets import WebSocketError


class Kupala:
    def __init__(
        self,
        package_name: str,
        *,
        routes: Routes,
        debug: bool = False,
        middleware: typing.Sequence[Middleware] = (),
        websocket_middleware: typing.Sequence[WebSocketMiddleware] = (),
        asgi_middleware: typing.Sequence[ASGIMiddlewareWrapper] = (),
        commands: typing.Sequence[click.Command] = (),
        error_handlers: typing.Mapping[type[Exception], ErrorHandler] | None = None,
    ) -> None:
        self.name = package_name
        self.routes = routes
        self.debug = debug
        self.commands = commands
        self.middleware = list(middleware)
        self.websocket_middleware = list(websocket_middleware)
        self.error_handlers = {
            BaseHTTPError: http_error_handler,
            HTTPException: http_error_handler,
            WebSocketError: websocket_error_handler,
            **(error_handlers or {}),
        }
        # ExceptionMiddleware resolves handlers by MRO, so a catch-all left in this map would match
        # every error and return before ServerErrorMiddleware can re-raise it for the server to log.
        # Starlette splits it out the same way.
        self.server_error_handler = self.error_handlers.pop(Exception, server_error_handler)

        asgi_middleware = [
            ASGIMiddlewareWrapper(ServerErrorMiddleware, handler=self.server_error_handler),
            *asgi_middleware,
            ASGIMiddlewareWrapper(ExceptionMiddleware, handlers=self.error_handlers),
        ]
        app = Router(
            lifespan=self.lifespan,
            routes=routes.compile(
                tuple(self.middleware),
                tuple(self.websocket_middleware),
            ),
        )
        for cls, args, kwargs in reversed(asgi_middleware):
            app = cls(app, *args, **kwargs)
        self._asgi_app = app

    @contextlib.asynccontextmanager
    async def lifespan(self, app: typing.Self) -> typing.AsyncGenerator[dict[str, typing.Any]]:
        yield {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        scope[INVOCATION_CONTEXT_KEY] = InvocationContext(scope=InjectionScope(bindings={Kupala: self}))
        await self._asgi_app(scope, receive, send)

    def cli(self) -> None:
        pass
