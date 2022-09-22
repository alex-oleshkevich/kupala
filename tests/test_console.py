import click
from unittest import mock

from kupala.application import App


def test_calls_console_command() -> None:
    spy = mock.MagicMock()

    @click.command
    def callme() -> None:
        spy()

    app = App(__name__, "key!")
    app.commands.add_command(callme)
    try:
        app.cli("callme")
    except SystemExit:
        pass
    finally:
        assert spy.called
