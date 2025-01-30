from __future__ import annotations

import typing

from starception import install_error_handler
from starlette.applications import Lifespan, Starlette
from starlette.middleware import Middleware
from starlette.routing import BaseRoute
from starlette.types import ExceptionHandler

from kupala.extensions import Extension


class Kupala(Starlette):
    """A Kupala application."""

    def __init__(
        self,
        debug: bool = False,
        routes: typing.Sequence[BaseRoute] | None = None,
        middleware: typing.Sequence[Middleware] | None = None,
        exception_handlers: typing.Mapping[typing.Any, ExceptionHandler] | None = None,
        on_startup: typing.Sequence[typing.Callable[[], typing.Any]] | None = None,
        on_shutdown: typing.Sequence[typing.Callable[[], typing.Any]] | None = None,
        lifespan: Lifespan[Kupala] | None = None,
        extensions: typing.Sequence[Extension] | None = None,
    ) -> None:
        super().__init__(debug, routes, middleware, exception_handlers, on_startup, on_shutdown, lifespan)

        for extension in extensions or []:
            extension.install(self)

        if debug:
            install_error_handler()
