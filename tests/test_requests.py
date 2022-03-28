import io
import pytest
import typing as t
from imia import AnonymousUser, LoginState, UserToken

from kupala.http.middleware import Middleware
from kupala.http.middleware.request_parser import RequestParserMiddleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Routes
from kupala.storages.storages import Storage
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


@pytest.fixture()
def form_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "client": ('0.0.0.0', '8080'),
        "headers": [
            [b"accept", b"text/html"],
            [b"content-type", b"application/x-www-form-urlencoded"],
            [b'cookie', b'key=value'],
            [b'x-key', b'1'],
            [b'x-multi', b'1'],
            [b'x-multi', b'2'],
        ],
    }

    async def receive(*args: t.Any) -> dict:
        return {
            "type": "http.request",
            "body": b"id=1&email=root@localhost",
            "more_body": False,
        }

    return Request(scope, receive)


@pytest.fixture()
def json_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            [b"content-type", b"application/json"],
            [b"accept", b"application/json"],
        ],
    }

    async def receive(*args: t.Any) -> dict:
        return {
            "type": "http.request",
            "body": b'{"key":"value", "key2": 2}',
            "more_body": False,
        }

    return Request(scope, receive)


@pytest.fixture()
def xhr_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [
            [b"content-type", b"application/json"],
            [b"x-requested-with", b"XMLHttpRequest"],
        ],
    }

    async def receive(*args: t.Any) -> dict:
        return {
            "type": "http.request",
            "body": b'{"key":"value", "key2": 2}',
            "more_body": False,
        }

    return Request(scope, receive)


@pytest.fixture()
def https_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "headers": [],
    }

    async def receive(*args: t.Any) -> dict:
        return {
            "type": "http.request",
            "body": b'{"key":"value", "key2": 2}',
            "more_body": False,
        }

    return Request(scope, receive)


def test_request_is_singleton() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "headers": [],
    }
    request = Request(scope)
    request2 = Request(scope)
    assert request is request2


def test_wants_json(json_request: Request, form_request: Request, xhr_request: Request) -> None:
    assert json_request.wants_json
    assert not form_request.wants_json
    assert not xhr_request.wants_json


def test_is_json(json_request: Request, form_request: Request, xhr_request: Request) -> None:
    assert json_request.is_json
    assert not form_request.is_json


def test_is_post(json_request: Request) -> None:
    assert json_request.is_post


def test_secure(form_request: Request, https_request: Request) -> None:
    assert https_request.secure
    assert not form_request.secure


def test_is_xhr(form_request: Request, xhr_request: Request) -> None:
    assert xhr_request.is_xhr
    assert not form_request.is_xhr


def test_ip(form_request: Request) -> None:
    assert form_request.ip == '0.0.0.0'


def test_url_matches() -> None:
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": (b"example.com", 80),
            "query_string": b"csrf-token=TOKEN",
            "path": "/account/login",
            "headers": {},
        }
    )
    assert request.url_matches(r'/account/login')
    assert request.url_matches(r'.*ogin')
    assert request.url_matches(r'/account/*')
    assert not request.url_matches(r'/admin')


def test_full_url_matches() -> None:
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("example.com", 80),
            "query_string": b"csrf-token=TOKEN",
            "path": "/account/login",
            "headers": {},
        }
    )
    assert request.full_url_matches(r'http://example.com')
    assert request.full_url_matches(r'http://example.com/account/*')
    assert request.full_url_matches(r'http://example.com/account/login')
    assert not request.full_url_matches(r'http://another.com/account/login')


def test_query_params() -> None:
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("example.com", 80),
            "query_string": b"token=TOKEN&enable=true&count=10&items=a&items=b&int=1&int=2",
            "path": "/account/login",
            "headers": {},
        }
    )
    assert request.query_params.get('token') == 'TOKEN'
    assert request.query_params.get_bool('enable') is True
    assert request.query_params.get_list('items') == ['a', 'b']
    assert request.query_params.get_list('int', int) == [1, 2]
    assert request.query_params.get_int('count') == 10
    assert request.query_params.get_int('count_missing', 42) == 42
    assert request.query_params.get_int('enable') is None


def test_file_uploads(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def upload_view(request: Request) -> JSONResponse:
        return JSONResponse(
            [
                {
                    'filename': file.filename,
                    'content': await file.read_string(),
                    'content-type': file.content_type,
                }
                for file in request.files.getlist('files')
            ]
        )

    routes.add('/', upload_view, methods=['post'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json', 'multipart', 'urlencoded'])],
    )
    client = TestClient(app)

    file1 = io.BytesIO('праўда'.encode())
    file2 = io.StringIO('file2')
    response = client.post(
        '/',
        data={'text': 'data'},
        files=[
            ('files', ('file1.txt', file1, 'text/plain')),
            ('files', file2),
        ],
    )
    assert response.status_code == 200
    assert response.json() == [
        {'filename': 'file1.txt', 'content-type': 'text/plain', 'content': 'праўда'},
        {'filename': 'files', 'content-type': '', 'content': 'file2'},
    ]


@pytest.mark.asyncio
async def test_file_upload_store(test_app_factory: TestAppFactory, routes: Routes, storage: Storage) -> None:
    async def upload_view(request: Request) -> JSONResponse:
        file = request.files.get('file')
        filename = ''
        if file:
            filename = await file.save(storage, 'newfile.txt')

        return JSONResponse(filename)

    routes.add('/', upload_view, methods=['post'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json', 'multipart', 'urlencoded'])],
    )

    client = TestClient(app)

    file1 = io.BytesIO(b'content')
    response = client.post(
        '/',
        data={'text': 'data'},
        files=[('file', ('file1.txt', file1, 'text/plain'))],
    )
    assert response.status_code == 200
    filename = response.json()

    assert await storage.exists(filename)
    file = await storage.get(filename)
    assert await file.read() == b'content'


@pytest.mark.asyncio
async def test_file_upload_store_without_filename(
    test_app_factory: TestAppFactory, routes: Routes, storage: Storage
) -> None:
    async def upload_view(request: Request) -> JSONResponse:
        filename = ''
        file = request.files.get('file')
        if file:
            filename = await file.save(storage, 'uploads')

        return JSONResponse(filename)

    routes.add('/', upload_view, methods=['post'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json', 'multipart', 'urlencoded'])],
    )
    client = TestClient(app)

    file1 = io.BytesIO(b'content')
    response = client.post(
        '/',
        data={'text': 'data'},
        files=[('file', file1)],
    )
    assert response.status_code == 200
    filename = response.json()
    assert '.bin' in filename
    assert await storage.exists(filename)


def test_request_auth(form_request: Request) -> None:
    form_request.scope['auth'] = UserToken(AnonymousUser(), LoginState.ANONYMOUS)
    assert isinstance(form_request.user, AnonymousUser)


def test_request_cookies(form_request: Request) -> None:
    assert form_request.cookies.get('key') == 'value'


def test_request_headers(form_request: Request) -> None:
    assert form_request.headers.get('x-key') == '1'
    assert form_request.headers.getlist('x-multi') == ['1', '2']


@pytest.mark.asyncio
async def test_request_data(test_app_factory: TestAppFactory, routes: Routes) -> None:
    def json_view(request: Request) -> JSONResponse:
        return JSONResponse(request.data)  # type: ignore

    def form_view(request: Request) -> JSONResponse:
        return JSONResponse(dict(request.data))  # type: ignore

    routes.add('/json', json_view, methods=['post'])
    routes.add('/form', form_view, methods=['post'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json', 'multipart', 'urlencoded'])],
    )
    client = TestClient(app)
    assert client.post('/json', json={'data': 'content'}).json() == {'data': 'content'}
    assert client.post('/form', data={'data': 'content'}).json() == {'data': 'content'}
