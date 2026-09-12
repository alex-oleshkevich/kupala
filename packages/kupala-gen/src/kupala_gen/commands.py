import click

from kupala.commands import Commands
from kupala_gen.loading import GeneratorGroup


def build_gen_command(commands: Commands) -> click.Group:
    """Build a fresh generator command tree."""

    @commands.group("gen")
    def gen() -> None:
        """Generate code."""

    @gen.command("new")
    def new() -> None:
        """Create a new project."""

    @gen.group("add", cls=GeneratorGroup)
    def add() -> None:
        """Add a feature to the current project."""

    return gen
