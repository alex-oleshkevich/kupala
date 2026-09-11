"""Discover the generators installed packages contribute."""

import importlib.metadata
import logging

import click

# a package ships a generator by naming a click command here, and `add` answers with it
GENERATOR_GROUP = "kupala.generators"

logger = logging.getLogger(__name__)


def load_generators(group: click.Group) -> None:
    """Add every generator an installed package contributes to `group`.

    A generator *is* the command, where a command-line plugin is a callable that registers one; that
    difference is why this does not go through `kupala.cli.load_plugins`. Loading happens here
    rather than on import so one broken package is reported and skipped, not fatal.
    """

    for entry_point in importlib.metadata.entry_points(group=GENERATOR_GROUP):
        try:
            command = entry_point.load()
        except Exception as exc:  # noqa: BLE001 - a third-party module may raise anything on import
            logger.warning("Ignoring generator %r, which failed to load: %s", entry_point.name, exc)
            continue

        if not isinstance(command, click.Command):
            logger.warning(
                "Ignoring generator %r: expected a click command, got %s.",
                entry_point.name,
                type(command).__name__,
            )
            continue

        group.add_command(command)
