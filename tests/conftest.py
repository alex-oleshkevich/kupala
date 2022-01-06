import pytest
import typing
from starlette.types import ASGIApp

from kupala.app.base import BaseApp


class TestApp(BaseApp):
    pass


class TestAppFactory(typing.Protocol):
    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> TestApp:
        ...


class TestASGIFactory(typing.Protocol):
    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> ASGIApp:
        ...


@pytest.fixture
def test_app_factory() -> TestAppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> TestApp:
        kwargs.setdefault('debug', True)
        return TestApp(*args, **kwargs)

    return factory


@pytest.fixture
def test_asgi_factory() -> TestASGIFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> ASGIApp:
        return TestApp(*args, **kwargs).create_asgi_app()

    return factory
