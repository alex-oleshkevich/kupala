from starlette.routing import Router
from starlette.types import ASGIApp, Receive, Scope, Send
from unittest import mock

from kupala.http import Host, PlainTextResponse, Request, Response, Route
from kupala.http.middleware import Middleware
from tests.conftest import TestClientFactory


def test_host(test_client_factory: TestClientFactory) -> None:
    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    client = test_client_factory(routes=[Host("example.com", asgi)])

    response = client.get("/", headers={"host": "example.com"})
    assert response.status_code == 200
    assert response.text == "ok"


def test_host_calls_middleware(test_client_factory: TestClientFactory) -> None:
    spy = mock.MagicMock()

    def example_middleware(app: ASGIApp) -> ASGIApp:
        async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
            spy()
            await app(scope, receive, send)

        return middleware

    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    client = test_client_factory(
        routes=[
            Host("example.com", asgi, middleware=[Middleware(example_middleware)]),
        ]
    )

    client.get("/", headers={"host": "example.com"})
    spy.assert_called_once()


def test_host_calls_guards(test_client_factory: TestClientFactory) -> None:
    guard_called = mock.MagicMock()

    def guard(request: Request) -> None:
        guard_called()

    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    client = test_client_factory(routes=[Host("example.com", asgi, guards=[guard])])

    client.get("/", headers={"host": "example.com"})
    guard_called.assert_called_once()


def test_constructs_url_to_nested_route() -> None:
    def index_view(request: Request) -> Response:
        return Response("ok")

    router = Router(
        [
            Host(
                "example.com",
                routes=[
                    Route("/", index_view, name="index"),
                    Route("/dashboard", index_view, name="dashboard"),
                ],
            )
        ]
    )

    assert router.url_path_for("index") == "/"
    assert router.url_path_for("dashboard") == "/dashboard"


def test_constructs_url_to_nested_route_with_middleware() -> None:
    def example_middleware(app: ASGIApp) -> ASGIApp:
        async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
            await app(scope, receive, send)

        return middleware

    def index_view(request: Request) -> Response:
        return Response("ok")

    router = Router(
        [
            Host(
                "example.com",
                routes=[
                    Route("/", index_view, name="index"),
                    Route("/dashboard", index_view, name="dashboard"),
                ],
                middleware=[Middleware(example_middleware)],
            )
        ]
    )

    assert router.url_path_for("index") == "/"
    assert router.url_path_for("dashboard") == "/dashboard"
