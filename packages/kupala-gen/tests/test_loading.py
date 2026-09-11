import importlib.metadata
import logging
import typing

import click
import pytest
from click.testing import CliRunner

from kupala.commands import Commands
from kupala_gen.commands import build_gen_command
from kupala_gen.loading import GENERATOR_GROUP


class StubEntryPoint:
    """An entry point already holding its target, so a test needs no importable module."""

    def __init__(self, name: str, target: typing.Any) -> None:
        self.name = name
        self._target = target

    def load(self) -> typing.Any:
        if isinstance(self._target, BaseException):
            raise self._target
        return self._target


def install(monkeypatch: pytest.MonkeyPatch, *points: StubEntryPoint) -> None:
    def entry_points(group: str) -> list[StubEntryPoint]:
        return list(points) if group == GENERATOR_GROUP else []

    monkeypatch.setattr(importlib.metadata, "entry_points", entry_points)


class TestGenerators:
    """A generator is a `kupala.generators` entry point and answers under `add`."""

    def test_a_generator_becomes_a_subcommand_of_add(self, monkeypatch: pytest.MonkeyPatch) -> None:
        @click.command("widget")
        def widget() -> None:
            click.echo("widget generated")

        install(monkeypatch, StubEntryPoint("widget", widget))
        gen = build_gen_command(Commands())

        result = CliRunner().invoke(gen, ["add", "widget"])
        assert result.exit_code == 0
        assert "widget generated" in result.output

    def test_a_generator_is_visible_in_help(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install(monkeypatch, StubEntryPoint("widget", click.Command("widget")))
        gen = build_gen_command(Commands())

        result = CliRunner().invoke(gen, ["add", "--help"])
        assert result.exit_code == 0
        assert "widget" in result.output

    def test_a_generator_that_fails_to_load_is_skipped(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        install(monkeypatch, StubEntryPoint("widget", RuntimeError("no such module")))
        gen = build_gen_command(Commands())

        with caplog.at_level(logging.WARNING):
            assert CliRunner().invoke(gen, ["add"]).exit_code == 2

        assert "failed to load" in caplog.text

    def test_a_generator_that_is_not_a_command_is_skipped(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        install(monkeypatch, StubEntryPoint("widget", "not a command"))
        gen = build_gen_command(Commands())

        with caplog.at_level(logging.WARNING):
            assert CliRunner().invoke(gen, ["add"]).exit_code == 2

        assert "expected a click command" in caplog.text
