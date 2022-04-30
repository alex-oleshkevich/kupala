from __future__ import annotations

import pytest

from kupala.application import App
from kupala.di import InjectionError, injectable
from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_to_injectable(test_app_factory: TestAppFactory) -> None:
    class WannaBeInjectable:
        pass

    def factory(app: App) -> WannaBeInjectable:
        return WannaBeInjectable()

    app = test_app_factory()
    app.di.make_injectable(WannaBeInjectable, from_app_factory=factory)
    assert isinstance(app.di.make(WannaBeInjectable), WannaBeInjectable)


def test_make_raises_for_missing_service(test_app_factory: TestAppFactory) -> None:
    class WannaBeInjectable:
        pass

    with pytest.raises(InjectionError):
        test_app_factory().di.make(WannaBeInjectable)


class WannaBeInjectable:
    pass


def test_to_request_injectable(test_app_factory: TestAppFactory, routes: Routes) -> None:
    if getattr(WannaBeInjectable, 'from_request', None):  # pragma: nocover
        # fixme: a hack to remove "from_request" attribute from module-level class WannaBeInjectable if present
        WannaBeInjectable.from_request = None  # type: ignore

    def view(injection: WannaBeInjectable) -> PlainTextResponse:
        return PlainTextResponse(injection.__class__.__name__)

    routes.add('/', view)
    app = test_app_factory(routes=routes)
    app.di.make_injectable(WannaBeInjectable, from_request_factory=lambda r: WannaBeInjectable())
    client = TestClient(app)
    assert client.get('/').text == 'WannaBeInjectable'


# APP INJECTABLE DECORATOR


def _via_injectable_factory(app: App) -> ViaInjectableDecorator:
    return ViaInjectableDecorator()


@injectable(from_app_factory=_via_injectable_factory)
class ViaInjectableDecorator:
    pass


def test_injectable_decorator(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory()
    assert isinstance(app.di.make(ViaInjectableDecorator), ViaInjectableDecorator)


# REQUEST INJECTABLE DECORATOR


def _via_request_injectable_factory(request: Request) -> ViaRequestInjectableDecorator:
    return ViaRequestInjectableDecorator()


@injectable(from_request_factory=_via_request_injectable_factory)
class ViaRequestInjectableDecorator:
    pass


def test_request_injectable_decorator(test_app_factory: TestAppFactory, routes: Routes) -> None:
    def view(injection: ViaRequestInjectableDecorator) -> PlainTextResponse:
        return PlainTextResponse(injection.__class__.__name__)

    routes.add('/', view)
    app = test_app_factory(routes=routes)
    client = TestClient(app)
    assert client.get('/').text == 'ViaRequestInjectableDecorator'
