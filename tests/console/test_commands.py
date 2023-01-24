import click
import pytest
import typing
from click.testing import CliRunner
from starlette.applications import Starlette
from unittest import mock

from kupala.console import ConsoleContext, Group


@pytest.fixture
def root() -> click.Group:
    @click.group(cls=Group)
    @click.pass_context
    def cli(context: click.Context) -> None:
        context.obj = ConsoleContext(app=Starlette())

    return cli


def test_app_context_is_not_required_if_not_asked(root: click.Group) -> None:
    @root.command
    def command() -> None:
        click.echo("hello")

    runner = CliRunner()
    result = runner.invoke(command, obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "hello\n"


def test_calls_command_decorator_with_sync_callable(root: click.Group) -> None:
    @root.command
    @click.argument("name")
    def command(name: str) -> None:
        click.echo(f"hello {name}!")

    runner = CliRunner()
    result = runner.invoke(command, ["world"], obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "hello world!\n"


def test_calls_command_decorator_with_async_callable(root: click.Group) -> None:
    @root.command
    @click.argument("name")
    async def command(name: str) -> None:
        click.echo(f"hello {name}!")

    runner = CliRunner()
    result = runner.invoke(command, ["world"], obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "hello world!\n"


def test_calls_command_decorator_with_params(root: click.Group) -> None:
    @root.command(name="testname")
    @click.argument("name")
    def command(name: str) -> None:  # pragma: nocover
        ...

    runner = CliRunner()
    result = runner.invoke(command, ["--help"], obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert "Usage: testname" in result.output


def test_injects_app_context(root: click.Group) -> None:
    @root.command
    @click.argument("name")
    def command(name: str, app: Starlette) -> None:
        click.echo(app.__class__.__name__)

    runner = CliRunner()
    result = runner.invoke(command, ["world"], obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "Starlette\n"


def test_group_without_arguments(root: click.Group) -> None:
    @root.group
    def group() -> None:
        ...

    @group.command()
    def subcommand() -> None:
        click.echo("hello")

    runner = CliRunner()
    result = runner.invoke(root, ["group", "subcommand"], obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "hello\n"


def test_group_with_arguments(root: click.Group) -> None:
    @root.group(name="group2")
    def group() -> None:
        ...

    @group.command()
    async def subcommand() -> None:
        click.echo("hello")

    runner = CliRunner()
    result = runner.invoke(root, ["group2", "subcommand"], obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "hello\n"


def test_group_with_async_subcommand(root: click.Group) -> None:
    @root.group()
    def group() -> None:
        ...

    @group.command()
    async def subcommand() -> None:
        click.echo("hello")

    runner = CliRunner()
    result = runner.invoke(root, ["group", "subcommand"], obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "hello\n"


def test_populates_commands_from_entrypoint() -> None:
    mock_entry_point = mock.MagicMock()
    mock_entry_point.name = "thirdparty"
    mock_entry_point.load = lambda: third_party_group
    with mock.patch("importlib.metadata.entry_points", return_value=[mock_entry_point]):

        @click.group(cls=Group)
        def cli() -> None:
            ...

        third_party_group = Group()

        @third_party_group.command("callme")
        def third_party_command() -> None:
            click.echo("hello")

        typing.cast(Group, cli).populate_from_entrypoints()

        runner = CliRunner()
        result = runner.invoke(cli, ["thirdparty", "callme"], obj=ConsoleContext(app=Starlette()))
        assert result.exit_code == 0
        assert result.output == "hello\n"


def test_injects_annotated_dependencies(root: click.Group) -> None:
    class Dep:
        ...

    Dependency = typing.Annotated[Dep, lambda: Dep()]

    @root.command()
    def command(dep: Dependency) -> None:
        click.echo(dep.__class__.__name__)

    runner = CliRunner()
    result = runner.invoke(command, obj=ConsoleContext(app=Starlette()))
    assert result.exit_code == 0
    assert result.output == "Dep\n"
