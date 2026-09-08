import typing

import pytest
from starlette.types import Scope

type ScopeType = typing.Literal["http", "websocket", "lifespan"]
type ScopeEndpoint = tuple[str, int]
type ScopeHeaders = typing.Sequence[tuple[bytes, bytes]]


class ScopeOverrides(typing.TypedDict, total=False):
    type: ScopeType
    asgi: typing.Mapping[str, str]
    http_version: str
    method: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: ScopeHeaders
    client: ScopeEndpoint | None
    server: ScopeEndpoint | None
    state: typing.Mapping[str, typing.Any]
    extensions: typing.Mapping[str, typing.Any]
    subprotocols: typing.Sequence[str]
    path_params: typing.Mapping[str, str]
    app: typing.Any
    router: typing.Any
    endpoint: typing.Any
    user: typing.Any
    session: typing.Any


class ScopeFactory(typing.Protocol):
    @typing.overload
    def __call__(self, **overrides: typing.Unpack[ScopeOverrides]) -> Scope: ...

    @typing.overload
    def __call__(self, **overrides: typing.Any) -> Scope: ...


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
