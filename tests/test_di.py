from __future__ import annotations

import pytest
import typing

from kupala.application import Kupala
from kupala.di import InjectionError
from kupala.responses import PlainTextResponse
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


class Injectable:
    @classmethod
    def from_app(cls, app: Kupala) -> Injectable:
        return cls()


def test_to_injectable() -> None:
    class WannaBeInjectable:
        pass

    def factory(app: Kupala) -> WannaBeInjectable:
        return WannaBeInjectable()

    app = Kupala()
    app.di.to_injectable(WannaBeInjectable, factory)
    assert isinstance(app.di.make(WannaBeInjectable), WannaBeInjectable)


def test_make_raises_for_missing_service() -> None:
    class WannaBeInjectable:
        pass

    with pytest.raises(InjectionError):
        Kupala().di.make(WannaBeInjectable)


class WannaBeInjectable:
    pass


def test_to_request_injectable() -> None:
    if getattr(WannaBeInjectable, 'from_request', None):
        WannaBeInjectable.from_request = None  # type: ignore

    def view(injection: WannaBeInjectable) -> PlainTextResponse:
        return PlainTextResponse(injection.__class__.__name__)

    app = Kupala()
    app.routes.add('/', view)
    app.di.to_request_injectable(WannaBeInjectable, lambda r: WannaBeInjectable())
    client = TestClient(app)
    assert client.get('/').text == 'WannaBeInjectable'
