from __future__ import annotations

import contextlib
import dataclasses
import inspect
import typing

import anyio
import click
from starception import install_error_handler
from starlette.applications import Lifespan, Starlette
from starlette.middleware import Middleware
from starlette.routing import BaseRoute
from starlette.types import ExceptionHandler

from kupala.dependency_resolvers import DependencyResolver


def multi_lifespan(*lifespan: Lifespan) -> None:
    @contextlib.asynccontextmanager
    async def handler(app: Starlette) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        async with contextlib.AsyncExitStack() as stack:
            combined = {}
            for ls in lifespan:
                state = await stack.enter_async_context(ls(app))
                if state:
                    combined.update(state)
            yield combined

    return handler


T = typing.TypeVar("T")


type AppInitializer = typing.Callable[[Kupala], typing.AsyncContextManager[None]]


@dataclasses.dataclass
class AppConfig:
    commands: list[click.Command] = dataclasses.field(default_factory=list)
    middleware: list[Middleware] = dataclasses.field(default_factory=list)
    routes: list[BaseRoute] = dataclasses.field(default_factory=list)
    initializers: list[AppInitializer] = dataclasses.field(default_factory=list)
    state: dict[object, typing.Any] = dataclasses.field(default_factory=dict)
    dependency_resolvers: dict[typing.Any, DependencyResolver] = dataclasses.field(default_factory=dict)
    exception_handlers: dict[typing.Any, ExceptionHandler] = dataclasses.field(default_factory=dict)


class Extension(typing.Protocol):
    def configure_application(self, app_config: AppConfig) -> None: ...


class Kupala(Starlette):
    """A Kupala application."""

    def __init__(
        self,
        debug: bool = False,
        routes: typing.Sequence[BaseRoute] = (),
        middleware: typing.Sequence[Middleware] = (),
        exception_handlers: typing.Mapping[typing.Any, ExceptionHandler] | None = None,
        lifespan: typing.Sequence[Lifespan[Kupala]] = (),
        commands: typing.Sequence[click.Command] = (),
        initializers: typing.Sequence[AppInitializer] = (),
        extensions: typing.Sequence[Extension] = (),
        state: typing.Mapping[object, typing.Any] | None = None,
    ) -> None:
        install_error_handler()
        _app_lifespan = multi_lifespan(*lifespan, self.initialize)

        app_config = AppConfig(
            commands=list(commands),
            middleware=list(middleware),
            routes=list(routes),
            initializers=list(initializers),
            state=dict(state or {}),
            exception_handlers=dict(exception_handlers or {}),
        )
        for extension in extensions:
            extension.configure_application(app_config)

        self.commands = app_config.commands
        self.initializers = app_config.initializers

        super().__init__(
            debug,
            lifespan=_app_lifespan,
            routes=app_config.routes,
            middleware=app_config.middleware,
            exception_handlers=app_config.exception_handlers,
        )
        self.state.dependency_resolvers = app_config.dependency_resolvers
        for state_key, state_value in app_config.state.items():
            setattr(self.state, state_key, state_value)

    @contextlib.asynccontextmanager
    async def initialize(self, app: typing.Self) -> typing.AsyncGenerator[None, None]:
        async with contextlib.AsyncExitStack() as stack:
            for initializer in self.initializers:
                await stack.enter_async_context(initializer(app))
            yield

    def cli_plugin(self, app: click.Group) -> None:
        """Install this application as Kupala CLI plugin."""

        for command in self.commands:
            app.add_command(command)

    def run_cli(self) -> None:
        """Run CLI application."""

        @click.group()
        @click.pass_context
        def cli(ctx: click.Context) -> None:
            ctx.obj = self

        self.cli_plugin(cli)

        async def main() -> None:
            async with self.initialize(self):
                try:
                    rv = cli(standalone_mode=False)
                    if inspect.iscoroutine(rv):
                        await rv
                except click.ClickException as exc:
                    click.secho("error: " + str(exc), err=True, fg="red")
                    raise SystemExit(exc.exit_code)

        anyio.run(main)
