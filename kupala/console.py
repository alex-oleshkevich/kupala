import dataclasses

import anyio
import click
import functools
import importlib.metadata
import inspect
import pprint
import typing
from starlette.applications import Starlette

from kupala.dependencies import Dependency, DependencyResolver, InvokeContext

_PS = typing.ParamSpec("_PS")
_RT = typing.TypeVar("_RT")


class StyledPrinter:
    def __init__(self, file: typing.IO[typing.Any] | None = None) -> None:
        self.file = file

    def print(self, text: str, **format_tokens: typing.Any) -> None:
        click.echo(text.format(**format_tokens), file=self.file)

    def header(self, text: str, **format_tokens: typing.Any) -> None:
        click.secho(text.format(**format_tokens), fg="cyan", bold=True, file=self.file)

    def text(self, text: str, **format_tokens: typing.Any) -> None:
        click.echo(text.format(**format_tokens), file=self.file)

    def success(self, text: str, **format_tokens: typing.Any) -> None:
        click.secho(text.format(**format_tokens), fg="green", file=self.file)

    def error(self, text: str, **format_tokens: typing.Any) -> None:
        click.secho(text.format(**format_tokens), fg="red", bold=True, file=self.file)

    def mark(self, text: str, **format_tokens: typing.Any) -> str:
        return click.style(text.format(**format_tokens), fg="blue")

    def dump(self, value: typing.Any) -> None:
        click.echo(pprint.pformat(value, indent=4, compact=True), file=self.file)


printer = StyledPrinter()


def async_command(fn: typing.Callable[_PS, typing.Awaitable[_RT]]) -> typing.Callable[_PS, _RT | None]:
    @functools.wraps(fn)
    def decorator(*args: _PS.args, **kwargs: _PS.kwargs) -> _RT | None:
        async def main() -> _RT:
            return await fn(*args, **kwargs)

        return anyio.run(main)

    return decorator


@dataclasses.dataclass
class ConsoleContext:
    app: Starlette


def wrap_callback(callback: typing.Callable[_PS, _RT | typing.Awaitable[_RT]]) -> typing.Callable:
    @functools.wraps(callback)
    def inner(context: click.Context, /, **kwargs: _PS.kwargs) -> _RT:
        def provide(value: typing.Any) -> typing.Any:
            return value

        overrides = {
            param_name: Dependency(
                type=type(param_value),
                param_name=param_name,
                factory=functools.partial(provide, param_value),
                optional=False,
                default_value=param_value,
            )
            for param_name, param_value in kwargs.items()
        }

        resolver_context = InvokeContext(app=context.obj.app)
        resolver = DependencyResolver.from_callable(callback, overrides=overrides)

        # sync callables executed in the threadpool which has no the click.Context
        # we have to call context as context manager to workaround it
        if not inspect.iscoroutinefunction(callback):

            def inner_function(**kwargs: _PS.kwargs) -> _RT | typing.Awaitable[_RT]:
                with context:
                    return callback(**kwargs)

            resolver.fn = inner_function

        return anyio.run(resolver.execute, resolver_context)

    return click.pass_context(inner)


def iterate_commands(cmd: click.Command) -> typing.Generator[click.Command, None, None]:
    if isinstance(cmd, click.Group):
        for subcmd in cmd.commands.values():
            yield from iterate_commands(subcmd)
    else:
        yield cmd


class Group(click.Group):
    def add_command(self, cmd: click.Command, name: str | None = None) -> None:
        for command in iterate_commands(cmd):
            if command.callback:
                command.callback = wrap_callback(command.callback)
        super().add_command(cmd, name)

    @typing.overload
    def group(self, __func: typing.Callable[..., typing.Any]) -> click.Group:  # pragma: no cover
        ...

    @typing.overload
    def group(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Callable[[typing.Callable[..., typing.Any]], click.Group]:  # pragma: no cover
        ...

    def group(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Union[typing.Callable[[typing.Callable[..., typing.Any]], click.Group], click.Group]:
        func: typing.Callable | None = None
        if args and callable(args[0]):
            func = args[0]
            args = ()

        def decorator(f: typing.Callable) -> click.Group:
            kwargs["cls"] = Group
            group = click.group(*args, **kwargs)(f)
            self.add_command(group)
            return group

        if func is not None:
            return decorator(func)

        return decorator

    @typing.overload
    def command(self, __func: typing.Callable[..., typing.Any]) -> click.Command:  # pragma: no cover
        ...

    @typing.overload
    def command(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Callable[[typing.Callable[..., typing.Any]], click.Command]:  # pragma: no cover
        ...

    def command(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Union[click.Command, typing.Callable[[typing.Callable[..., typing.Any]], click.Command]]:
        func: typing.Callable | None = None

        if args and callable(args[0]):
            func = args[0]
            args = ()

        def decorator(f: typing.Callable) -> click.Command:
            f = wrap_callback(f)
            command: click.Command = click.command(*args, **kwargs)(f)
            self.add_command(command)
            return command

        if func is not None:
            return decorator(func)

        return decorator

    def populate_from_entrypoints(self) -> None:
        for entry_point in importlib.metadata.entry_points(group="kupala.commands"):
            command = entry_point.load()
            self.add_command(command, entry_point.name)


def create_console_app(app: Starlette) -> click.Group:
    @click.group(cls=Group)
    @click.pass_context
    def group(context: click.Context) -> None:  # pragma: no cover
        context.obj = ConsoleContext(app=app)

    typing.cast(Group, group).populate_from_entrypoints()

    app.state.cli = group
    return group
