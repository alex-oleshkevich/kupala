from __future__ import annotations

import typing
from starlette.applications import Starlette
from starlette.datastructures import State
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute

from kupala.dependencies import Injector

_T = typing.TypeVar("_T")


class Kupala(Starlette):
    state: State

    def __init__(
        self,
        *,
        debug: bool = False,
        routes: typing.Sequence[BaseRoute] | None = None,
        middleware: typing.Sequence[Middleware] | None = None,
        exception_handlers: typing.Mapping[
            typing.Any,
            typing.Callable[
                [Request, Exception],
                typing.Union[Response, typing.Awaitable[Response]],
            ],
        ]
        | None = None,
        lifespan: typing.Callable[["Starlette"], typing.AsyncContextManager] | None = None,
        dependencies: Injector | None = None,
    ) -> None:
        super().__init__(
            debug=debug, routes=routes, middleware=middleware, exception_handlers=exception_handlers, lifespan=lifespan
        )
        self.dependencies = dependencies or Injector()


App = Kupala
