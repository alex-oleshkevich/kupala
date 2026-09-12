import importlib.metadata
import typing

import click
import pytest
from click.testing import CliRunner

from kupala.commands import Commands
from kupala_gen.commands import build_gen_command
from kupala_gen.generators.model import generator as model_generator
from kupala_gen.generators.route import generator as route_generator
from kupala_gen.loading import GENERATOR_GROUP, GeneratorGroup


class StubDistribution:
    def __init__(self, name: str) -> None:
        self.name = name


class StubEntryPoint:
    def __init__(self, name: str, target: typing.Any, *, provider: str | None = "plugin") -> None:
        self.name = name
        self.value = f"{provider or 'orphan'}.generators:{name}"
        self.dist = StubDistribution(provider) if provider is not None else None
        self.target = target
        self.loads = 0

    def load(self) -> typing.Any:
        self.loads += 1
        if isinstance(self.target, BaseException):
            raise self.target

        return self.target


def install(monkeypatch: pytest.MonkeyPatch, *points: StubEntryPoint) -> None:
    def entry_points(group: str) -> list[StubEntryPoint]:
        return list(points) if group == GENERATOR_GROUP else []

    monkeypatch.setattr(importlib.metadata, "entry_points", entry_points)


def generator_command(name: str, output: str = "generated") -> click.Command:
    @click.command(name)
    def command() -> None:
        click.echo(output)

    return command


class TestGenerators:
    def test_help_and_completion_do_not_load_generators(self, monkeypatch: pytest.MonkeyPatch) -> None:
        widget = StubEntryPoint("widget", generator_command("widget"), provider="widgets")
        other = StubEntryPoint("other", generator_command("other"), provider=None)
        install(monkeypatch, widget, other)
        gen = build_gen_command(Commands())

        result = CliRunner().invoke(gen, ["add", "--help"])
        add = typing.cast(GeneratorGroup, gen.commands["add"])
        completions = add.shell_complete(click.Context(add), "wid")

        assert result.exit_code == 0
        assert "widget" in result.output
        assert "widgets" in result.output
        assert "unknown distribution" in result.output
        assert [item.value for item in completions] == ["widget"]
        assert widget.loads == other.loads == 0

    def test_help_and_invocation_load_only_the_selected_generator(self, monkeypatch: pytest.MonkeyPatch) -> None:
        widget = StubEntryPoint("widget", generator_command("widget", "widget generated"))
        other = StubEntryPoint("other", generator_command("other"))
        install(monkeypatch, other, widget)
        gen = build_gen_command(Commands())

        help_result = CliRunner().invoke(gen, ["add", "widget", "--help"])
        result = CliRunner().invoke(gen, ["add", "widget"])

        assert help_result.exit_code == 0
        assert result.exit_code == 0
        assert result.output == "widget generated\n"
        assert widget.loads == 2
        assert other.loads == 0

    def test_a_broken_generator_does_not_block_another(self, monkeypatch: pytest.MonkeyPatch) -> None:
        broken = StubEntryPoint("broken", RuntimeError("secret import detail"))
        working = StubEntryPoint("working", generator_command("working", "works"))
        install(monkeypatch, broken, working)
        runner = CliRunner()
        gen = build_gen_command(Commands())

        failure = runner.invoke(gen, ["add", "broken"])
        success = runner.invoke(gen, ["add", "working"])

        assert failure.exit_code == 1
        assert "Could not load generator 'broken'" in failure.output
        assert "secret import detail" not in failure.output
        assert success.exit_code == 0
        assert success.output == "works\n"
        assert broken.loads == 1
        assert working.loads == 1

    def test_duplicate_names_block_only_that_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        first = StubEntryPoint("widget", generator_command("widget"), provider="first")
        second = StubEntryPoint("widget", generator_command("widget"), provider="second")
        working = StubEntryPoint("working", generator_command("working", "works"))
        install(monkeypatch, second, working, first)
        runner = CliRunner()
        gen = build_gen_command(Commands())

        help_result = runner.invoke(gen, ["add", "--help"])
        failure = runner.invoke(gen, ["add", "widget"])
        success = runner.invoke(gen, ["add", "working"])

        assert "unavailable" in help_result.output
        assert "first" in failure.output
        assert "second" in failure.output
        assert first.loads == second.loads == 0
        assert success.output == "works\n"

    def test_a_generator_must_be_a_click_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        point = StubEntryPoint("widget", "not a command")
        install(monkeypatch, point)

        result = CliRunner().invoke(build_gen_command(Commands()), ["add", point.name])

        assert result.exit_code == 1
        assert "expected a Click command" in result.output

    def test_unknown_generator_is_regular_click_behavior(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install(monkeypatch)
        gen = build_gen_command(Commands())

        help_result = CliRunner().invoke(gen, ["add", "--help"])
        result = CliRunner().invoke(gen, ["add", "missing"])

        assert help_result.exit_code == 0
        assert result.exit_code == 2
        assert "No such command 'missing'" in result.output

    @pytest.mark.parametrize(
        ("command", "output"),
        [(model_generator, "model\n"), (route_generator, "route\n")],
    )
    def test_bundled_generator_entry_points_execute(self, command: click.Command, output: str) -> None:
        result = CliRunner().invoke(command)

        assert result.exit_code == 0
        assert result.output == output
