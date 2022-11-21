import os
import pathlib
import pytest
import typing
from starlette.applications import Starlette
from starlette.routing import BaseRoute
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from kupala.dependencies import DiMiddleware, Injector
from kupala.middleware import Middleware
from kupala.routing import Routes


class TestAppFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self,
        debug: bool = True,
        middleware: list[Middleware] | None = None,
        routes: Routes | typing.Iterable[BaseRoute] | None = None,
        **kwargs: typing.Any,
    ) -> Starlette:
        ...


class TestClientFactory(typing.Protocol):  # pragma: nocover
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
def test_app_factory(tmp_path: os.PathLike) -> TestAppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> Starlette:
        injector = Injector()
        kwargs.setdefault("debug", True)
        kwargs.setdefault("routes", Routes())
        kwargs.setdefault("middleware", [])
        kwargs["middleware"].append(
            Middleware(DiMiddleware, injector=injector),
        )
        return Starlette(*args, **kwargs)

    return factory


@pytest.fixture
def test_client_factory(test_app_factory: TestAppFactory) -> TestClientFactory:
    def factory(**kwargs: typing.Any) -> TestClient:
        raise_server_exceptions = kwargs.pop("raise_server_exceptions", True)
        app = kwargs.pop("app", test_app_factory(**kwargs))
        return TestClient(app, raise_server_exceptions=raise_server_exceptions)

    return typing.cast(TestClientFactory, factory)


@pytest.fixture
def routes() -> Routes:
    return Routes()


@pytest.fixture()
def jinja_template_path(tmp_path: os.PathLike) -> pathlib.Path:
    return pathlib.Path(str(tmp_path))
