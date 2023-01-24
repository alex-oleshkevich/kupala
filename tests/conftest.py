import asyncio
import os
import pytest
import typing
from starlette.applications import Starlette
from starlette.authentication import SimpleUser
from starlette.routing import BaseRoute
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from kupala.middleware import Middleware
from kupala.routing import Routes


class AppFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self,
        debug: bool = True,
        middleware: list[Middleware] | None = None,
        routes: Routes | typing.Iterable[BaseRoute] | None = None,
        **kwargs: typing.Any,
    ) -> Starlette:
        ...


class ClientFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self,
        debug: bool = True,
        middleware: list[Middleware] | None = None,
        routes: Routes | typing.Iterable[BaseRoute] | None = None,
        raise_server_exceptions: bool = True,
        app: ASGIApp | None = None,
        **kwargs: typing.Any,
    ) -> TestClient:
        ...


@pytest.fixture
def test_app_factory(tmp_path: os.PathLike) -> AppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> Starlette:
        kwargs.setdefault("debug", True)
        kwargs.setdefault("routes", Routes())
        kwargs.setdefault("middleware", [])
        return Starlette(*args, **kwargs)

    return factory


@pytest.fixture
def test_client_factory(test_app_factory: AppFactory) -> ClientFactory:
    def factory(**kwargs: typing.Any) -> TestClient:
        raise_server_exceptions = kwargs.pop("raise_server_exceptions", True)
        app = kwargs.pop("app", test_app_factory(**kwargs))
        return TestClient(app, raise_server_exceptions=raise_server_exceptions)

    return typing.cast(ClientFactory, factory)


@pytest.fixture
def routes() -> Routes:
    return Routes()


class User(SimpleUser):
    @property
    def identity(self) -> str:
        return self.username


@pytest.fixture()
def user() -> User:
    return User(username="root")


@pytest.fixture(scope="session")
def event_loop() -> typing.Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
