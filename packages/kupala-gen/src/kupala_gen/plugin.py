"""Expose the generator commands to the Kupala command line.

Registered through the `kupala.commands` entry point group, which `kupala.cli.load_plugins` calls
with the root group. Generator commands answer without an application: scaffolding a project is
the one thing you do before there is one.
"""

import click

from kupala_gen.commands import commands


def register(cli: click.Group) -> None:
    """Add the generator commands to `cli`."""

    for command in commands.compile():
        cli.add_command(command)
