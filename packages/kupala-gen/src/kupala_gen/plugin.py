from kupala.commands import Commands
from kupala_gen.commands import build_gen_command


def register(commands: Commands) -> None:
    """Add the generator commands to the current CLI build."""

    build_gen_command(commands)
