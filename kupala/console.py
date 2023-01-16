import dataclasses

import anyio
import click
import functools
import importlib.metadata
import inspect
import pprint
import typing
from starlette.applications import Starlette

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
    parameters = inspect.signature(callback, eval_str=True).parameters
    context_parameter_name: str = ""
    click_context_parameter_name: str = ""
    for parameter in parameters.values():
        if parameter.annotation == ConsoleContext:
            context_parameter_name = parameter.name
        if parameter.annotation == click.Context:
            click_context_parameter_name = parameter.name

    @functools.wraps(callback)
    def inner(context: click.Context, /, *args: _PS.args, **kwargs: _PS.kwargs) -> _RT:
        if context_parameter_name:
            app_context: ConsoleContext = context.obj
            assert context.obj, "No console context object set."
            assert isinstance(
                context.obj, ConsoleContext
            ), f"context.obj must be an instance of {ConsoleContext.__name__}. It is: {type(context)}."
            kwargs[context_parameter_name] = app_context

        if click_context_parameter_name:
            kwargs[click_context_parameter_name] = context

        if inspect.iscoroutinefunction(callback):

            async def main() -> _RT:
                return await typing.cast(typing.Awaitable[_RT], callback(*args, **kwargs))

            return anyio.run(main)
        return typing.cast(_RT, callback(*args, **kwargs))

    return click.pass_context(inner)


class Group(click.Group):
    def add_command(self, cmd: click.Command, name: str | None = None) -> None:
        if cmd.callback:
            cmd.callback = wrap_callback(cmd.callback)
        super().add_command(cmd, name)

    @typing.overload
    def group(self, __func: typing.Callable[..., typing.Any]) -> click.Group:
        ...

    @typing.overload
    def group(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Callable[[typing.Callable[..., typing.Any]], click.Group]:
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
    def command(self, __func: typing.Callable[..., typing.Any]) -> click.Command:
        ...

    @typing.overload
    def command(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Callable[[typing.Callable[..., typing.Any]], click.Command]:
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
    def group(context: click.Context) -> None:
        context.obj = ConsoleContext(app=app)

    typing.cast(Group, group).populate_from_entrypoints()
    return group
