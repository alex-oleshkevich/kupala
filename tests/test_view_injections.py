from __future__ import annotations

import typing
from unittest import mock

from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.routing import Route
from kupala.testclient import TestClient


class _RequestInjectable:
    @classmethod
    def from_request(cls, request: Request) -> _RequestInjectable:
        return cls()


class _AsyncRequestInjectable:
    @classmethod
    async def from_request(cls, request: Request) -> _AsyncRequestInjectable:
        return cls()


class _AppInjectable:
    @classmethod
    def from_app(cls, app: Kupala) -> _AppInjectable:
        return cls()


class _AsyncAppInjectable:
    @classmethod
    async def from_app(cls, app: Kupala) -> _AsyncAppInjectable:
        return cls()


class _InjectableContextManager:
    def __init__(self) -> None:
        self.enter_spy = mock.MagicMock()
        self.exit_spy = mock.MagicMock()

    def __enter__(self) -> None:
        self.enter_spy()

    def __exit__(self, *args: typing.Any) -> None:
        self.exit_spy()

    @classmethod
    def from_request(cls, request: Request) -> typing.Generator[_InjectableContextManager, None, None]:
        instance = cls()
        with instance:
            yield instance


class _InjectableAsyncContextManager:
    def __init__(self) -> None:
        self.enter_spy = mock.MagicMock()
        self.exit_spy = mock.MagicMock()

    async def __aenter__(self) -> None:
        self.enter_spy()

    async def __aexit__(self, *args: typing.Any) -> None:
        self.exit_spy()

    @classmethod
    async def from_request(cls, request: Request) -> typing.AsyncGenerator[_InjectableAsyncContextManager, None]:
        instance = cls()
        async with instance:
            yield instance


def test_injects_from_request() -> None:
    def view(injectable: _RequestInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.json() == '_RequestInjectable'


def test_injects_from_request_async() -> None:
    def view(injectable: _AsyncRequestInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.json() == '_AsyncRequestInjectable'


def test_injectable_generators() -> None:
    instance: _InjectableContextManager | None = None

    def view(injectable: _InjectableContextManager) -> JSONResponse:
        nonlocal instance
        instance = injectable
        return JSONResponse(injectable.__class__.__name__)

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.json() == '_InjectableContextManager'
    assert instance
    instance.enter_spy.assert_called_once()
    instance.exit_spy.assert_called_once()


def test_injectable_async_generators() -> None:
    instance: _InjectableAsyncContextManager | None = None

    def view(injectable: _InjectableAsyncContextManager) -> JSONResponse:
        nonlocal instance
        instance = injectable
        return JSONResponse(injectable.__class__.__name__)

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.json() == '_InjectableAsyncContextManager'
    assert instance
    instance.enter_spy.assert_called_once()
    instance.exit_spy.assert_called_once()


def test_injects_from_app() -> None:
    def view(injectable: _AppInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.json() == '_AppInjectable'


def test_injects_from_app_async() -> None:
    def view(injectable: _AsyncAppInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.json() == '_AsyncAppInjectable'
