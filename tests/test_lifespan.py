import pytest
import typing
from contextlib import asynccontextmanager

from kupala.application import App
from kupala.exceptions import ShutdownError, StartupError
from kupala.http import Request, route
from kupala.http.responses import Response
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_lifespan(test_app_factory: TestAppFactory) -> None:
    enter_called = False
    exit_called = False

    @asynccontextmanager
    async def handler(app: App) -> typing.AsyncIterator[None]:
        nonlocal enter_called, exit_called
        enter_called = True
        yield
        exit_called = True

    @route("/")
    def view(_: Request) -> Response:
        return Response("content")

    app = test_app_factory(lifespan_handlers=[handler], routes=[view])

    with TestClient(app) as client:
        client.get("/")
        assert not exit_called
    assert enter_called
    assert exit_called


def test_lifespan_boot_error(test_app_factory: TestAppFactory) -> None:
    @asynccontextmanager
    async def handler(app: App) -> typing.AsyncIterator[None]:
        raise TypeError()
        yield

    app = test_app_factory(lifespan_handlers=[handler])

    with pytest.raises(StartupError):
        with TestClient(app):
            pass


def test_lifespan_shutdown_error(test_app_factory: TestAppFactory) -> None:
    @asynccontextmanager
    async def handler(_: App) -> typing.AsyncIterator[None]:
        yield
        raise TypeError()

    app = test_app_factory(lifespan_handlers=[handler])

    with pytest.raises(ShutdownError):
        with TestClient(app):
            pass
