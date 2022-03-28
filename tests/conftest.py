import jinja2
import os
import pathlib
import pytest
import typing

from kupala.application import App
from kupala.contracts import TemplateRenderer
from kupala.http import Routes
from kupala.http.middleware import Middleware
from kupala.storages.storages import LocalStorage, Storage
from kupala.templating import JinjaRenderer
from kupala.testclient import TestClient


class TestAppFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self, middleware: list[Middleware] | None = None, routes: Routes | None = None, **kwargs: typing.Any
    ) -> App:
        ...


class TestClientFactory(typing.Protocol):  # pragma: nocover
    def __call__(
        self, middleware: list[Middleware] | None = None, routes: Routes | None = None, **kwargs: typing.Any
    ) -> TestClient:
        ...


@pytest.fixture
def test_app_factory() -> TestAppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> App:
        kwargs.setdefault('debug', True)
        kwargs.setdefault('app_class', App)
        kwargs.setdefault('routes', Routes())
        kwargs.setdefault('secret_key', 't0pSekRet!')
        app_class = kwargs.pop('app_class')
        app = app_class(*args, **kwargs)

        if renderer := kwargs.get('renderer'):
            if isinstance(renderer, JinjaRenderer):
                renderer._env.globals['static'] = app.static_url

        return app

    return factory


@pytest.fixture
def test_client_factory(test_app_factory: TestAppFactory) -> TestClientFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> TestClient:
        return TestClient(test_app_factory(*args, **kwargs))

    return factory


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
