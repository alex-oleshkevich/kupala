import typing

import pytest
from starlette.testclient import TestClient
from starlette.types import Scope

from kupala.applications import Kupala
from kupala.routing import Routes
from tests.types import ScopeFactory


@pytest.fixture
def app() -> Kupala:
    return Kupala("tests", routes=Routes())


@pytest.fixture
def test_client(app: Kupala) -> typing.Generator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture
def scope_f(
    type: typing.Literal["http", "websocket", "lifespan"] = "http",
) -> ScopeFactory:
    def factory(**overrides: typing.Any) -> Scope:
        path = typing.cast(str, overrides.get("path", "/"))
        scope: dict[str, typing.Any] = {
            "type": type,
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "state": {},
            "extensions": {},
            "subprotocols": [],
            "path_params": {},
            "app": None,
            "router": None,
            "endpoint": None,
            "user": None,
            "session": None,
        }
        scope.update(overrides)
        return scope

    return factory
