from __future__ import annotations

import pytest
import typing

from kupala.application import Kupala
from kupala.di import InjectionError, injectable
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse
from kupala.testclient import TestClient


def test_prefer_for_instance() -> None:
    class SomeProtocol(typing.Protocol):
        ...

    app = Kupala()
    app.di.prefer_for(SomeProtocol, 'value')
    assert app.di.make(SomeProtocol) == 'value'


def test_prefer_for_factory() -> None:
    class SomeProtocol(typing.Protocol):
        ...

    class Implementation:
        pass

    app = Kupala()
    app.di.prefer_for(SomeProtocol, lambda app: Implementation())
    assert isinstance(app.di.make(SomeProtocol), Implementation)


def test_to_injectable() -> None:
    class WannaBeInjectable:
        pass

    def factory(app: Kupala) -> WannaBeInjectable:
        return WannaBeInjectable()

    app = Kupala()
    app.di.make_injectable(WannaBeInjectable, from_app_factory=factory)
    assert isinstance(app.di.make(WannaBeInjectable), WannaBeInjectable)


def test_make_raises_for_missing_service() -> None:
    class WannaBeInjectable:
        pass

    with pytest.raises(InjectionError):
        Kupala().di.make(WannaBeInjectable)


class WannaBeInjectable:
    pass


def test_to_request_injectable() -> None:
    if getattr(WannaBeInjectable, 'from_request', None):  # pragma: nocover
        # fixme: a hack to remove "from_request" attribute from module-level class WannaBeInjectable if present
        WannaBeInjectable.from_request = None  # type: ignore

    def view(injection: WannaBeInjectable) -> PlainTextResponse:
        return PlainTextResponse(injection.__class__.__name__)

    app = Kupala()
    app.routes.add('/', view)
    app.di.make_injectable(WannaBeInjectable, from_request_factory=lambda r: WannaBeInjectable())
    client = TestClient(app)
    assert client.get('/').text == 'WannaBeInjectable'


# APP INJECTABLE DECORATOR


def _via_injectable_factory(app: Kupala) -> ViaInjectableDecorator:
    return ViaInjectableDecorator()


@injectable(from_app_factory=_via_injectable_factory)
class ViaInjectableDecorator:
    pass


def test_injectable_decorator() -> None:
    app = Kupala()
    assert isinstance(app.di.make(ViaInjectableDecorator), ViaInjectableDecorator)


# REQUEST INJECTABLE DECORATOR


def _via_request_injectable_factory(request: Request) -> ViaRequestInjectableDecorator:
    return ViaRequestInjectableDecorator()


@injectable(from_request_factory=_via_request_injectable_factory)
class ViaRequestInjectableDecorator:
    pass


def test_request_injectable_decorator() -> None:
    def view(injection: ViaRequestInjectableDecorator) -> PlainTextResponse:
        return PlainTextResponse(injection.__class__.__name__)

    app = Kupala()
    app.routes.add('/', view)
    client = TestClient(app)
    assert client.get('/').text == 'ViaRequestInjectableDecorator'
