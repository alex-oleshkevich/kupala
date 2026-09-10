import click
from click.testing import CliRunner

from kupala_gen.commands import gen
from kupala_gen.plugin import register


class TestRegister:
    def test_adds_the_generator_group(self) -> None:
        cli = click.Group()
        register(cli)
        assert cli.commands == {"gen": gen}

    def test_the_group_lists_its_commands(self) -> None:
        result = CliRunner().invoke(gen, ["--help"])
        assert result.exit_code == 0
        assert "new" in result.output
        assert "add" in result.output

    def test_a_leaf_command_runs(self) -> None:
        result = CliRunner().invoke(gen, ["new"])
        assert result.exit_code == 0

    def test_a_nested_group_needs_a_command(self) -> None:
        result = CliRunner().invoke(gen, ["add"])
        assert result.exit_code == 2
