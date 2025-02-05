from __future__ import annotations

import contextvars
import typing

import click
from starception import install_error_handler
from starlette.applications import Lifespan, Starlette
from starlette.middleware import Middleware
from starlette.routing import BaseRoute
from starlette.types import ExceptionHandler

from kupala.extensions import Extension


class Kupala(Starlette):
    """A Kupala application."""

    _current_app: contextvars.ContextVar[Kupala] = contextvars.ContextVar("kupala_current_app")

    def __init__(
        self,
        debug: bool = False,
        routes: typing.Sequence[BaseRoute] | None = None,
        middleware: typing.Sequence[Middleware] | None = None,
        exception_handlers: typing.Mapping[typing.Any, ExceptionHandler] | None = None,
        on_startup: typing.Sequence[typing.Callable[[], typing.Any]] | None = None,
        on_shutdown: typing.Sequence[typing.Callable[[], typing.Any]] | None = None,
        lifespan: Lifespan[Kupala] | None = None,
        extensions: typing.Mapping[typing.Hashable, Extension] | None = None,
        commands: typing.Sequence[click.Command] | None = None,
    ) -> None:
        super().__init__(debug, routes, middleware, exception_handlers, on_startup, on_shutdown, lifespan)

        self.commands = commands or []
        for extension in extensions or []:
            extension.install(self)

        install_error_handler()

    def cli_plugin(self, app: click.Group) -> None:
        """Install this application as Kupala CLI plugin."""
        self._current_app.set(self)

        for command in self.commands:
            app.add_command(command)

    def run_cli(self) -> None:
        """Run CLI application."""
        app = click.Group()
        self.cli_plugin(app)
        app()

    @classmethod
    def current(cls) -> Kupala:
        return cls._current_app.get()
