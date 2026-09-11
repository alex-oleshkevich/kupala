import importlib.metadata
import pathlib

import pytest
from click.testing import CliRunner

from kupala import cli
from kupala.commands import Commands
from kupala_gen.commands import build_gen_command
from kupala_gen.plugin import register


def install_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    point = importlib.metadata.EntryPoint(
        name="gen",
        value="kupala_gen.plugin:register",
        group=cli.PLUGIN_GROUP,
    )

    def entry_points(*, group: str) -> list[importlib.metadata.EntryPoint]:
        return [point] if group == cli.PLUGIN_GROUP else []

    monkeypatch.setattr(importlib.metadata, "entry_points", entry_points)


class TestRegister:
    def test_adds_the_generator_group(self) -> None:
        commands = Commands()
        register(commands)
        assert [command.name for command in commands.compile()] == ["gen"]

    def test_the_group_lists_its_commands(self) -> None:
        gen = build_gen_command(Commands())
        result = CliRunner().invoke(gen, ["--help"])
        assert result.exit_code == 0
        assert "new" in result.output
        assert "add" in result.output

    def test_a_leaf_command_runs(self) -> None:
        gen = build_gen_command(Commands())
        result = CliRunner().invoke(gen, ["new"])
        assert result.exit_code == 0

    def test_a_nested_group_needs_a_command(self) -> None:
        gen = build_gen_command(Commands())
        result = CliRunner().invoke(gen, ["add"])
        assert result.exit_code == 2

    def test_factory_builds_distinct_trees(self) -> None:
        first = build_gen_command(Commands())
        second = build_gen_command(Commands())

        assert first is not second
        assert first.commands["add"] is not second.commands["add"]
        assert first.commands["new"] is not second.commands["new"]

    @pytest.mark.parametrize(
        "application",
        [None, "malformed", "never.imported:app", "broken_gen_app:app"],
    )
    def test_bootstrap_commands_ignore_application_configuration(
        self,
        application: str | None,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        install_plugin(monkeypatch)
        monkeypatch.syspath_prepend(str(tmp_path))
        (tmp_path / "broken_gen_app.py").write_text("import secret_missing_dependency\n")
        if application is None:
            monkeypatch.delenv(cli.APP_ENV_VAR, raising=False)
        else:
            monkeypatch.setenv(cli.APP_ENV_VAR, application)

        runner = CliRunner()
        for args in (["gen", "--help"], ["gen", "new"]):
            result = runner.invoke(cli.build_cli(None), args)

            assert result.exit_code == 0
            assert "secret_missing_dependency" not in result.output
