from kupala import commands
from kupala.cli import load_plugins

APP_GROUP = "kupala.generator"

cli = commands.Commands()


@commands.group("gen")
def gen() -> None:
    """Generate code."""
    # a package ships its own generators by registering them on one of the groups below
    load_plugins(add, APP_GROUP)


@gen.command("new")
def new() -> None:
    """Create a new project."""


@gen.command("new-module")
def new_module() -> None:
    """Add a module to the current project."""


@gen.group("add")
def add() -> None:
    """Add a feature to the current project."""
