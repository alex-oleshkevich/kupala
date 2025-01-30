import typing
from http.cookiejar import CookieJar

import factory
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

HeaderTypes = typing.Union[
    httpx.Headers,
    typing.Mapping[str, str],
    typing.Mapping[bytes, bytes],
    typing.Sequence[tuple[str, str]],
    typing.Sequence[tuple[bytes, bytes]],
]

CookieTypes = typing.Union[
    httpx.Cookies, CookieJar, dict[str, str], list[tuple[str, str]]
]


class AsyncTestClient(httpx.AsyncClient):
    def __init__(
        self,
        app: ASGIApp,
        follow_redirects: bool = False,
        base_url="http://testserver",
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
    ) -> None:
        transport = httpx.ASGITransport(app)
        super().__init__(
            cookies=cookies,
            headers=headers,
            transport=transport,
            base_url=base_url,
            follow_redirects=follow_redirects,
        )


class RequestScopeFactory(factory.DictFactory):
    type: str = "http"
    method: str = "GET"
    http_version: str = "1.1"
    server: tuple[str, int] = ("testserver", 80)
    client: tuple[str, int] = ("testclient", 80)
    scheme: str = "http"
    path: str = "/"
    raw_path: bytes = b"/"
    query_string: bytes = b""
    root_path: str = ""
    app: Starlette = factory.LazyFunction(
        lambda: Starlette(
            debug=False,
            routes=[
                Route("/", lambda: Response("index"), name="home"),
                Mount("/static", Response("static"), name="static"),
                Mount("/media", Response("media"), name="media"),
            ],
        )
    )
    user: typing.Any | None = None
    session: dict[str, typing.Any] = factory.LazyFunction(dict)
    state: dict[str, typing.Any] = factory.LazyFunction(dict)
    headers: tuple[tuple[bytes, bytes], ...] = (
        (b"host", b"testserver"),
        (b"connection", b"close"),
        (b"user-agent", b"testclient"),
        (b"accept", b"*/*"),
    )


class RequestFactory(factory.Factory[Request]):
    scope: factory.SubFactory = factory.SubFactory(RequestScopeFactory)

    class Meta:
        model = Request
