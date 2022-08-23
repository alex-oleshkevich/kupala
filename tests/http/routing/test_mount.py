from starlette.routing import Router
from starlette.types import ASGIApp, Receive, Scope, Send
from unittest import mock

from kupala.http import Mount, PlainTextResponse, Request, Response, Route
from kupala.http.middleware import Middleware
from tests.conftest import TestClientFactory


def test_mount(test_client_factory: TestClientFactory) -> None:
    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    client = test_client_factory(routes=[Mount("/asgi", asgi)])

    response = client.get("/asgi")
    assert response.status_code == 200
    assert response.text == "ok"


def test_mount_calls_middleware(test_client_factory: TestClientFactory) -> None:
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
            Mount("/asgi", asgi, middleware=[Middleware(example_middleware)]),
        ]
    )

    client.get("/asgi")
    spy.assert_called_once()


def test_mount_calls_guards(test_client_factory: TestClientFactory) -> None:
    guard_called = mock.MagicMock()

    def guard(request: Request) -> None:
        guard_called()

    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    client = test_client_factory(routes=[Mount("/asgi", asgi, guards=[guard])])

    client.get("/asgi")
    guard_called.assert_called_once()


def test_constructs_url_to_nested_route(test_client_factory: TestClientFactory) -> None:
    def index_view(request: Request) -> Response:
        return Response("ok")

    router = Router(
        [
            Mount(
                "/admin",
                routes=[
                    Route("/", index_view, name="admin_index"),
                    Route("/dashboard", index_view, name="admin_dashboard"),
                ],
            )
        ]
    )

    assert router.url_path_for("admin_index") == "/admin/"
    assert router.url_path_for("admin_dashboard") == "/admin/dashboard"


def test_constructs_url_to_nested_route_with_middleware(test_client_factory: TestClientFactory) -> None:
    def example_middleware(app: ASGIApp) -> ASGIApp:
        async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
            await app(scope, receive, send)

        return middleware

    def index_view(request: Request) -> Response:
        return Response("ok")

    router = Router(
        [
            Mount(
                "/admin",
                routes=[
                    Route("/", index_view, name="admin_index"),
                    Route("/dashboard", index_view, name="admin_dashboard"),
                ],
                middleware=[Middleware(example_middleware)],
            )
        ]
    )

    assert router.url_path_for("admin_index") == "/admin/"
    assert router.url_path_for("admin_dashboard") == "/admin/dashboard"
