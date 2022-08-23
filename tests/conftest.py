import jinja2
import os
import pathlib
import pytest
import typing
from starlette.routing import BaseRoute
from starlette.types import ASGIApp

from kupala.application import App
from kupala.contracts import TemplateRenderer
from kupala.http import Routes
from kupala.http.middleware import Middleware
from kupala.storages.storages import LocalStorage, Storage
from kupala.templating import JinjaRenderer
from kupala.testclient import TestClient
from tests.utils import FormatRenderer


class TestAppFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self,
        debug: bool = True,
        middleware: list[Middleware] | None = None,
        routes: Routes | typing.Iterable[BaseRoute] | None = None,
        **kwargs: typing.Any,
    ) -> App:
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
def test_app_factory() -> TestAppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> App:
        renderer = kwargs.pop("renderer", FormatRenderer())
        kwargs.setdefault("debug", True)
        kwargs.setdefault("app_class", App)
        kwargs.setdefault("routes", Routes())
        kwargs.setdefault("secret_key", "t0pSekRet!")
        app_class = kwargs.pop("app_class")
        app = app_class(*args, **kwargs)
        app.renderer = renderer
        return app

    return factory


@pytest.fixture
def test_client_factory(test_app_factory: TestAppFactory) -> TestClientFactory:
    def factory(**kwargs: typing.Any) -> TestClient:
        raise_server_exceptions = kwargs.pop("raise_server_exceptions", True)

        kwargs.setdefault("app", test_app_factory(**kwargs))
        app = kwargs["app"]
        return TestClient(app, raise_server_exceptions=raise_server_exceptions)

    return typing.cast(TestClientFactory, factory)


@pytest.fixture
def routes() -> Routes:
    return Routes()


@pytest.fixture()
def storage(tmp_path: os.PathLike) -> Storage:
    return LocalStorage(tmp_path)


@pytest.fixture()
def jinja_template_path(tmp_path: os.PathLike) -> pathlib.Path:
    return pathlib.Path(str(tmp_path))


@pytest.fixture()
def jinja_env(jinja_template_path: str) -> jinja2.Environment:
    return jinja2.Environment(loader=jinja2.FileSystemLoader(jinja_template_path))


@pytest.fixture()
def jinja_renderer(jinja_env: jinja2.Environment) -> TemplateRenderer:
    return JinjaRenderer(jinja_env)


@pytest.fixture()
def format_renderer() -> TemplateRenderer:
    return FormatRenderer()
