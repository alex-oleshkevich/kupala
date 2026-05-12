import typing

import click

from kupala.exceptions import ExceptionHandler, HTTPError
from kupala.lifespan import Lifespan, lifespan_handler
from kupala.middleware import Middleware, build_asgi_middleware_stack
from kupala.routing import RouteGroup, Router
from kupala.types import ASGIApp, ASGIMiddleware, Receive, Scope, Send


class Kupala:
    def __init__(
        self,
        *,
        routes: RouteGroup,
        commands: typing.Sequence[click.Command] = (),
        lifespan: typing.Sequence[Lifespan] = (),
        middleware: typing.Sequence[Middleware] = (),
        asgi_middleware: typing.Sequence[ASGIMiddleware] = (),
        exception_handlers: typing.Mapping[type[Exception] | int, ExceptionHandler] | None = None,
    ) -> None:
        self.middleware = middleware
        self.exception_handlers = exception_handlers
        self.commands = commands
        self._router = Router(routes)
        self._lifespan = lifespan_handler(self, lifespan)
        self._asgi_middleware_stack = build_asgi_middleware_stack(asgi_middleware, typing.cast(ASGIApp, self._router))

    def cli(self) -> None: ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["state"]["app"] = self

        if scope["type"] == "lifespan":
            return await self._lifespan(scope, receive, send)

        try:
            await self._asgi_middleware_stack(scope, receive, send)
        except Exception as ex:
            match ex:
                case HTTPError():
                    pass
                case _:
                    pass
