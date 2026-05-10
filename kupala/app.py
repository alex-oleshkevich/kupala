import typing

import click

from kupala.exceptions import ExceptionHandler
from kupala.middleware import Middleware
from kupala.routing import RouteGroup, Router
from kupala.types import ASGIMiddleware, Receive, Scope, Send

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
        self.router = Router(routes)

    def cli(self) -> None: ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            route = self.router.match(scope)
            if not route:
                raise Exception()

        except BaseException:
            pass
