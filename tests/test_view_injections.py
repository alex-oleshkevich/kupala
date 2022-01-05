from __future__ import annotations

import pathlib
import typing
from unittest import mock

from kupala.application import Kupala
from kupala.requests import Cookies, FilesData, FormData, Headers, QueryParams, Request
from kupala.responses import JSONResponse, PlainTextResponse
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


def test_injects_cookies() -> None:
    def view(cookies: Cookies) -> PlainTextResponse:
        return PlainTextResponse(cookies.get('key'))

    app = Kupala(routes=[Route('/', view)])
    client = TestClient(app)
    response = client.get('/', cookies={'key': 'value'})
    assert response.text == 'value'


def test_injects_headers() -> None:
    def view(headers: Headers) -> PlainTextResponse:
        return PlainTextResponse(headers.get('x-key'))

    app = Kupala(routes=[Route('/', view)])
    client = TestClient(app)
    response = client.get('/', headers={'x-key': 'value'})
    assert response.text == 'value'


def test_injects_form_data() -> None:
    def view(data: FormData) -> PlainTextResponse:
        return PlainTextResponse(data.get('key', ''))

    app = Kupala(routes=[Route('/', view)])
    client = TestClient(app)
    response = client.get('/', data={'key': 'value'})
    assert response.text == 'value'


def test_injects_files(tmpdir: pathlib.Path) -> None:
    file_path = pathlib.Path(tmpdir / 'file.txt')
    file_path.write_bytes(b'value')

    async def view(data: FilesData) -> PlainTextResponse:
        file = data.get('file')
        assert file
        content = await file.read()
        return PlainTextResponse(data.get('key', content))

    app = Kupala(routes=[Route('/', view, methods=['post'])])
    client = TestClient(app)
    response = client.post('/', files=[('file', file_path.open('rb'))])
    assert response.text == 'value'


def test_injects_query_params() -> None:
    def view(data: QueryParams) -> PlainTextResponse:
        return PlainTextResponse(data.get('key', ''))

    app = Kupala(routes=[Route('/', view)])
    client = TestClient(app)
    response = client.get('/?key=value')
    assert response.text == 'value'
