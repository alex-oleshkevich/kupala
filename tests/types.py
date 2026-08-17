import typing

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
