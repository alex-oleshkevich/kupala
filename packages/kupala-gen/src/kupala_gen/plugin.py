import click

from kupala_gen.commands import gen


def register(cli: click.Group) -> None:
    cli.add_command(gen)
