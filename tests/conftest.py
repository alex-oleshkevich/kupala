import pytest
import typing
from starlette.types import ASGIApp

from kupala.app.base import BaseApp


class TestApp(BaseApp):
    pass


class TestAppFactory(typing.Protocol):
    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> TestApp:
        ...


@pytest.fixture
def test_app_factory() -> TestAppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> TestApp:
        kwargs.setdefault('debug', True)
        kwargs.setdefault('app_class', TestApp)
        app_class = kwargs.pop('app_class')
        return app_class(*args, **kwargs)

    return factory
