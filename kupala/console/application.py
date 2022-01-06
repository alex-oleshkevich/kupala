from __future__ import annotations

import anyio
import click
import functools
import inspect
import typing
import typing as t

if typing.TYPE_CHECKING:
    from kupala.app.base import BaseApp


def create_dispatcher(app: BaseApp, fn: t.Callable) -> t.Callable:
    fn_kwargs = t.get_type_hints(fn)

    @functools.wraps(fn)
    def dispatcher(**kwargs: t.Any) -> t.Any:
        for name, class_name in fn_kwargs.items():
            if hasattr(class_name, 'from_app'):
                kwargs[name] = class_name.from_app(app)

        if inspect.iscoroutinefunction(fn):

            async def async_dispatcher() -> t.Any:
                return await fn(**kwargs)

            return anyio.run(async_dispatcher)
        else:
            return fn(**kwargs)

    return dispatcher


def wrap_command(app: BaseApp, command: t.Union[click.Command, t.Callable]) -> click.Command:
    if isinstance(command, click.Group):
        if not command.callback:
            return command
        command.callback = create_dispatcher(app, command.callback)
        command.commands = {
            command_name: wrap_command(app, subcommand) for command_name, subcommand in command.commands.items()
        }
    elif isinstance(command, click.Command):
        if not command.callback:
            return command
        command.name = command.name.replace('-command', '') if command.name else command.name
        command.callback = create_dispatcher(app, command.callback)
    else:
        name = command.__name__.replace('_command', '')
        return click.Command(name, callback=create_dispatcher(app, command))
    return command


class ConsoleApplication:
    def __init__(self, app: BaseApp, commands: list[click.Command]) -> None:
        self.app = app
        self.commands = commands

    def run(self) -> int:
        @click.group()
        @click.pass_context
        def console_app(ctx: click.Context) -> None:
            ctx.ensure_object(dict)
            ctx.obj['app'] = self.app

        for command in self.commands:
            command = wrap_command(self.app, command)
            console_app.add_command(command)
        return console_app()
