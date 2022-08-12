from __future__ import annotations

import pytest
import typing
from unittest import mock

from kupala.di import InjectionError, InjectionRegistry
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Routes
from tests.conftest import TestClientFactory


class _RequestInjectable:
    pass


def make_request_injectable(registry: InjectionRegistry) -> typing.Callable[[Request], _RequestInjectable]:
    def factory(request: Request) -> _RequestInjectable:
        return _RequestInjectable()

    return factory


class _AsyncRequestInjectable:
    pass


def make_async_request_injectable(
    registry: InjectionRegistry,
) -> typing.Callable[[Request], typing.Awaitable[_AsyncRequestInjectable]]:
    async def factory(request: Request) -> _AsyncRequestInjectable:
        return _AsyncRequestInjectable()

    return factory


class _RequestInjectableContextManager:
    def __init__(self) -> None:
        self.enter_spy = mock.MagicMock()
        self.exit_spy = mock.MagicMock()

    def __enter__(self) -> None:
        self.enter_spy()

    def __exit__(self, *args: typing.Any) -> None:
        self.exit_spy()


def make_request_injectable_context_manager(
    registry: InjectionRegistry,
) -> typing.Callable[[Request], typing.Generator[_RequestInjectableContextManager, None, None]]:
    def factory(request: Request) -> typing.Generator[_RequestInjectableContextManager, None, None]:
        instance = _RequestInjectableContextManager()
        with instance:
            yield instance

    return factory


class _RequestInjectableAsyncContextManager:
    def __init__(self) -> None:
        self.enter_spy = mock.MagicMock()
        self.exit_spy = mock.MagicMock()

    async def __aenter__(self) -> None:
        self.enter_spy()

    async def __aexit__(self, *args: typing.Any) -> None:
        self.exit_spy()


def make_request_injectable_async_context_manager(
    registry: InjectionRegistry,
) -> typing.Callable[[Request], typing.AsyncGenerator[_RequestInjectableAsyncContextManager, None]]:
    async def factory(request: Request) -> typing.AsyncGenerator[_RequestInjectableAsyncContextManager, None]:
        instance = _RequestInjectableAsyncContextManager()
        async with instance:
            yield instance

    return factory


class _AppInjectable:
    pass


def make_app_injectable(registry: InjectionRegistry) -> _AppInjectable:
    return _AppInjectable()


class _AsyncAppInjectable:
    pass


def make_async_app_injectable(registry: InjectionRegistry) -> _AsyncAppInjectable:
    return _AsyncAppInjectable()


def test_injects_from_request(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(injectable: _RequestInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    client.app.dependencies.register_for_request(_RequestInjectable, make_request_injectable)

    response = client.get("/")
    assert response.json() == "_RequestInjectable"


def test_injects_from_request_async(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(injectable: _AsyncRequestInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    client.app.dependencies.register_for_request(_AsyncRequestInjectable, make_async_request_injectable)

    response = client.get("/")
    assert response.json() == "_AsyncRequestInjectable"


def test_injectable_generators(test_client_factory: TestClientFactory, routes: Routes) -> None:
    instance: _RequestInjectableContextManager | None = None

    def view(injectable: _RequestInjectableContextManager) -> JSONResponse:
        nonlocal instance
        instance = injectable
        return JSONResponse(injectable.__class__.__name__)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    client.app.dependencies.register_for_request(
        _RequestInjectableContextManager, make_request_injectable_context_manager
    )

    response = client.get("/")
    assert response.json() == "_RequestInjectableContextManager"
    assert instance
    instance.enter_spy.assert_called_once()
    instance.exit_spy.assert_called_once()


def test_injectable_async_generators(test_client_factory: TestClientFactory, routes: Routes) -> None:
    instance: _RequestInjectableAsyncContextManager | None = None

    def view(injectable: _RequestInjectableAsyncContextManager) -> JSONResponse:
        nonlocal instance
        instance = injectable
        return JSONResponse(injectable.__class__.__name__)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    client.app.dependencies.register_for_request(
        _RequestInjectableAsyncContextManager,
        make_request_injectable_async_context_manager,
    )

    response = client.get("/")
    assert response.json() == "_RequestInjectableAsyncContextManager"
    assert instance
    instance.enter_spy.assert_called_once()
    instance.exit_spy.assert_called_once()


def test_injects_from_app(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(injectable: _AppInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    client.app.dependencies.register(_AppInjectable, make_app_injectable)

    response = client.get("/")
    assert response.json() == "_AppInjectable"


def test_injects_from_app_async(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(injectable: _AsyncAppInjectable) -> JSONResponse:
        return JSONResponse(injectable.__class__.__name__)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    client.app.dependencies.register(_AsyncAppInjectable, make_async_app_injectable)

    response = client.get("/")
    assert response.json() == "_AsyncAppInjectable"


def test_injects_default_raises(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(injectable: str) -> JSONResponse:
        return JSONResponse(injectable)

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    with pytest.raises(InjectionError):
        response = client.get("/")
        assert response.json() is None


def test_injects_default_null(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(injectable: str = None) -> JSONResponse:
        return JSONResponse(injectable)

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    response = client.get("/")
    assert response.json() is None


def test_injects_default_non_null(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(injectable: str = "default") -> JSONResponse:
        return JSONResponse(injectable)

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    response = client.get("/")
    assert response.json() == "default"
