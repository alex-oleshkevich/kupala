import pytest
import typing

from kupala.application import Kupala


class TestApp(Kupala):
    pass


class TestAppFactory(typing.Protocol):  # pragma: nocover
    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> TestApp:
        ...


@pytest.fixture
def test_app_factory() -> TestAppFactory:
    def factory(*args: typing.Any, **kwargs: typing.Any) -> TestApp:
        kwargs.setdefault('debug', True)
        kwargs.setdefault('app_class', TestApp)
        app_class = kwargs.pop('app_class')
        app = app_class(*args, **kwargs)
        return app

    return factory
