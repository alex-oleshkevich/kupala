import typing as t
from unittest import mock

from kupala.application import App
from kupala.extensions import BaseExtension
from kupala.responses import TextResponse


def view(*args: t.Any) -> t.Any:
    return TextResponse("ok")


class _ExampleExtension(BaseExtension):
    def register(self, app: App):
        app["registered"] = True

    def bootstrap(self, app: App):
        app["boostrapped"] = True


def test_boots_extensions_for_asgi(app, test_client):
    app.routes.get("/", view)
    app.extensions.use(_ExampleExtension())
    test_client.get("/")

    assert app["registered"]
    assert app["boostrapped"]


def test_boots_extensions_for_console(app):
    with mock.patch("click.Group.__call__"):
        app.extensions.use(_ExampleExtension())
        app.run_cli()

        assert app["registered"]
        assert app["boostrapped"]
