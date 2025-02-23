import asyncio
import os
import typing

import pytest
from starlette.applications import Starlette
from starlette.authentication import SimpleUser
from starlette.routing import BaseRoute
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from kupala.middleware import Middleware
from kupala.routing import RouteGroup


class AppFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self,
        debug: bool = True,
        middleware: list[Middleware] | None = None,
        routes: typing.Iterable[BaseRoute] | None = None,
        **kwargs: typing.Any,
    ) -> Starlette: ...


class ClientFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self,
        debug: bool = True,
        middleware: list[Middleware] | None = None,
        routes: typing.Iterable[BaseRoute] | None = None,
        raise_server_exceptions: bool = True,
        app: ASGIApp | None = None,
        **kwargs: typing.Any,
    ) -> TestClient: ...


@pytest.fixture
def test_app_factory() -> AppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> Starlette:
        kwargs.setdefault("debug", True)
        kwargs.setdefault("routes", RouteGroup())
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
def routes() -> RouteGroup:
    return RouteGroup()


class User(SimpleUser):
    @property
    def identity(self) -> str:
        return self.username


@pytest.fixture()
def user() -> User:
    return User(username="root")
