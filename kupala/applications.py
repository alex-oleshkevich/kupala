import contextlib
import typing

import click
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.routing import Router
from starlette.types import Receive, Scope, Send

from kupala.dependencies import DependencyResolver
from kupala.error_handlers import (
    ErrorHandler,
    ErrorHandlers,
    http_error_handler,
    server_error_handler,
    websocket_error_handler,
)
from kupala.errors import BaseHTTPError
from kupala.middleware import Middleware
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
        asgi_middleware: typing.Sequence[ASGIMiddlewareWrapper] = (),
        commands: typing.Sequence[click.Command] = (),
        error_handlers: typing.Mapping[type[Exception], ErrorHandler] | None = None,
    ) -> None:
        self.name = package_name
        self.routes = routes
        self.debug = debug
        self.commands = commands
        self.middleware = list(middleware)
        self.services = DependencyResolver()
        self.error_handlers = ErrorHandlers(
            {
                BaseHTTPError: http_error_handler,
                HTTPException: http_error_handler,
                Exception: server_error_handler,
                WebSocketError: websocket_error_handler,
                **(error_handlers or {}),
            }
        )

        asgi_middleware = [
            ASGIMiddlewareWrapper(ServerErrorMiddleware, handler=server_error_handler),
            *asgi_middleware,
            ASGIMiddlewareWrapper(ExceptionMiddleware, handlers=error_handlers),
        ]
        app = Router(routes=routes.compile(self), lifespan=self.lifespan)
        for cls, args, kwargs in reversed(asgi_middleware):
            app = cls(app, *args, **kwargs)
        self._asgi_app = app

    @contextlib.asynccontextmanager
    async def lifespan(self, app: None) -> typing.AsyncGenerator[dict[str, typing.Any]]:
        yield {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        await self._asgi_app(scope, receive, send)

    def cli(self) -> None:
        pass
