from starlette.types import ASGIApp, Receive, Scope, Send
from unittest import mock

from kupala.http import Request, Response, route
from kupala.http.middleware import Middleware
from tests.conftest import TestClientFactory


def test_route(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def index(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=[index])
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "ok"


def test_route_calls_func_middleware(test_client_factory: TestClientFactory) -> None:
    spy = mock.MagicMock()

    def example_middleware(app: ASGIApp) -> ASGIApp:
        async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
            spy()
            await app(scope, receive, send)

        return middleware

    @route("/", middleware=[Middleware(example_middleware)])
    def index(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=[index])
    client.get("/")
    spy.assert_called_once()


def test_route_calls_class_middleware(test_client_factory: TestClientFactory) -> None:
    spy = mock.MagicMock()

    class Example:
        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            spy()
            await self.app(scope, receive, send)

    @route("/", middleware=[Middleware(Example)])
    def index(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=[index])
    client.get("/")
    spy.assert_called_once()


def test_route_calls_guards(test_client_factory: TestClientFactory) -> None:
    guard_called = mock.MagicMock()

    def guard(request: Request) -> None:
        guard_called()

    @route("/", guards=[guard])
    def index(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=[index])
    client.get("/")
    guard_called.assert_called_once()
