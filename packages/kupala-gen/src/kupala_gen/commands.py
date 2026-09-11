from kupala import Commands
from kupala_gen.loading import load_generators

commands = Commands()


@commands.group("gen")
def gen() -> None:
    """Generate code."""
    # loaded here rather than in `add`: click resolves a group's subcommand before it runs that
    # group's own callback, so a generator has to be attached before `add` is asked for one
    load_generators(add)


@gen.command("new")
def new() -> None:
    """Create a new project."""


@gen.command("new-module")
def new_module() -> None:
    """Add a module to the current project."""


@gen.group("add")
def add() -> None:
    """Add a feature to the current project."""
