import io
import os.path
import pytest
import typing as t
from deesk.drivers.fs import LocalFsDriver
from deesk.storage import Storage
from imia import AnonymousUser, LoginState, UserToken
from pathlib import Path

from kupala.application import Kupala
from kupala.ext.disks import StoragesProvider
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.routing import Route
from kupala.testclient import TestClient


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


def test_file_uploads() -> None:
    async def upload_view(request: Request) -> JSONResponse:
        files = await request.files()

        return JSONResponse(
            [
                {
                    'filename': file.filename,
                    'content': await file.read_string(),
                    'content-type': file.content_type,
                }
                for file in files.getlist('files')
            ]
        )

    app = Kupala(routes=[Route('/', upload_view, methods=['POST'])])
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


def test_file_upload_store(tmp_path: Path) -> None:
    async def upload_view(request: Request) -> JSONResponse:
        files = await request.files()
        file = files.get('file')
        filename = ''
        if file:
            filename = await file.save(tmp_path)

        return JSONResponse(filename)

    app = Kupala(
        routes=[Route('/', upload_view, methods=['POST'])],
        providers=[StoragesProvider(disks={'default': Storage(LocalFsDriver(tmp_path))}, default='default')],
    )
    app.bootstrap()
    client = TestClient(app)

    file1 = io.BytesIO(b'content')
    response = client.post(
        '/',
        data={'text': 'data'},
        files=[('file', ('file1.txt', file1, 'text/plain'))],
    )
    assert response.status_code == 200
    filename = response.json()
    assert os.path.exists(filename)
    with open(filename, 'r') as f:
        assert f.read() == 'content'


def test_file_upload_store_with_filename(tmp_path: Path) -> None:
    async def upload_view(request: Request) -> JSONResponse:
        files = await request.files()
        filename = ''
        file = files.get('file')
        if file:
            filename = await file.save(tmp_path, 'myfile.txt')
        return JSONResponse(filename)

    app = Kupala(
        routes=[Route('/', upload_view, methods=['POST'])],
        providers=[StoragesProvider(disks={'default': Storage(LocalFsDriver(tmp_path))}, default='default')],
    )
    app.bootstrap()
    client = TestClient(app)

    file1 = io.BytesIO(b'content')
    response = client.post(
        '/',
        data={'text': 'data'},
        files=[('file', ('file1.txt', file1, 'text/plain'))],
    )
    assert response.status_code == 200
    filename = response.json()
    assert 'myfile.txt' in filename


def test_file_upload_store_without_filename(tmp_path: Path) -> None:
    async def upload_view(request: Request) -> JSONResponse:
        files = await request.files()
        filename = ''
        file = files.get('file')
        if file:
            filename = await file.save(tmp_path)

        return JSONResponse(filename)

    app = Kupala(
        routes=[Route('/', upload_view, methods=['POST'])],
        providers=[StoragesProvider(disks={'default': Storage(LocalFsDriver(tmp_path))}, default='default')],
    )
    app.bootstrap()
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


def test_request_auth(form_request: Request) -> None:
    form_request.scope['auth'] = UserToken(AnonymousUser(), LoginState.ANONYMOUS)
    assert isinstance(form_request.user, AnonymousUser)
