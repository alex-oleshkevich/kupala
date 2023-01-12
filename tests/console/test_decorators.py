import click
from click.testing import CliRunner
from starlette.applications import Starlette

from kupala.console import ConsoleContext, async_command


def test_async_command_decorator() -> None:
    @click.command
    @async_command
    async def command() -> None:
        click.echo("hello")

    runner = CliRunner()
    result = runner.invoke(command, obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "hello\n"


def test_async_command_decorator_with_error() -> None:
    @click.command
    @async_command
    async def command() -> None:
        raise click.ClickException("error")

    runner = CliRunner()
    result = runner.invoke(command, obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 1
    assert result.output == "Error: error\n"
