import anyio
import click
import functools
import inspect
import typing as t

from kupala.container import Container


def create_dispatcher(container: Container, fn: t.Callable) -> t.Callable:
    @functools.wraps(fn)
    def dispatcher(*args: t.Any, **kwargs: t.Any) -> t.Any:
        if inspect.iscoroutinefunction(fn):

            async def async_dispatcher() -> t.Any:
                return await container.invoke(fn, extra_kwargs=kwargs)

            return anyio.run(async_dispatcher)
        else:
            return container.invoke(fn, extra_kwargs=kwargs)

    return dispatcher


def wrap_command(container: Container, command: t.Union[click.Command, t.Callable]) -> click.Command:
    if isinstance(command, click.Group):
        if not command.callback:
            return command
        command.callback = create_dispatcher(container, command.callback)
        command.commands = {
            command_name: wrap_command(container, subcommand) for command_name, subcommand in command.commands.items()
        }
    elif isinstance(command, click.Command):
        if not command.callback:
            return command
        command.callback = create_dispatcher(container, command.callback)
    else:
        name = command.__name__.replace('_command', '')
        return click.Command(name, callback=create_dispatcher(container, command))
    return command


class ConsoleApplication:
    def __init__(self, container: Container, commands: list[click.Command]) -> None:
        self.container = container
        self.commands = commands

    def run(self) -> int:
        @click.group()
        @click.pass_context
        def console_app(ctx: click.Context) -> None:
            ctx.ensure_object(dict)
            ctx.obj['app'] = self

        for command in self.commands:
            command = wrap_command(self.container, command)
            console_app.add_command(command)
        return console_app()
