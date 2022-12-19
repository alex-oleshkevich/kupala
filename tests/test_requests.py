import pytest
import typing as t

from kupala.authentication import AnonymousUser, AuthToken, LoginState
from kupala.requests import Request


@pytest.fixture()
def form_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "client": ("0.0.0.0", "8080"),
        "path": "/",
        "headers": [
            [b"accept", b"text/html"],
            [b"content-type", b"application/x-www-form-urlencoded"],
            [b"cookie", b"key=value"],
            [b"x-key", b"1"],
            [b"x-multi", b"1"],
            [b"x-multi", b"2"],
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
    assert request.query_params.get("token") == "TOKEN"
    assert request.query_params.get_bool("enable") is True
    assert request.query_params.get_list("items") == ["a", "b"]
    assert request.query_params.get_list("int", int) == [1, 2]
    assert request.query_params.get_int("count") == 10
    assert request.query_params.get_int("count_missing", 42) == 42
    assert request.query_params.get_int("enable") is None


def test_request_auth(form_request: Request) -> None:
    form_request.scope["auth"] = AuthToken(AnonymousUser(), LoginState.ANONYMOUS)
    assert isinstance(form_request.user, AnonymousUser)
