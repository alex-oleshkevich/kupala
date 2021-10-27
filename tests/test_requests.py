import pytest
import typing as t

from kupala.requests import Request


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