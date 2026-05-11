import typing

import click

from kupala.exceptions import ExceptionHandler
from kupala.middleware import Middleware, build_middleware_stack
from kupala.routing import RouteGroup, Router
from kupala.types import ASGIApp, ASGIMiddleware, Receive, Scope, Send

type Lifespan = typing.Callable[[Kupala], typing.AsyncGenerator[typing.Mapping[str, typing.Any]]]


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
        self.asgi_middleware = asgi_middleware
        self.exception_handlers = exception_handlers
        self.commands = commands
        self.lifespan = lifespan
        self._router = Router(routes)
        self._asgi_middleware_stack = build_middleware_stack(asgi_middleware, typing.cast(ASGIApp, self._router))

    def cli(self) -> None: ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self._asgi_middleware_stack(scope, receive, send)
        except BaseException:
            pass
