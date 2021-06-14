import typing as t

import click as click

from kupala.application import App
from kupala.extensions import Extension
from kupala.framework import commands


class ConsoleExtension(Extension):
    console_commands: list[click.Command] = [
        commands.mails_group,
    ]

    def __init__(self, commands_: t.Iterable[click.Command] = None) -> None:
        self.console_commands.extend(commands_ or [])

    def register(self, app: App) -> None:
        app.commands.extend(self.console_commands)
