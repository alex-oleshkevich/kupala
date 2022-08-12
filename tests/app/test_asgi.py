from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import Routes
from kupala.http.middleware import Middleware
from kupala.http.requests import Request
from kupala.http.responses import Response
from tests.conftest import TestClientFactory


def test_routes(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view() -> Response:
        return Response("ok")

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    assert client.get("/").text == "ok"


def test_middleware(test_client_factory: TestClientFactory, routes: Routes) -> None:
    class TestMiddleware:
        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            scope["key"] = "value"
            await self.app(scope, receive, send)

    def view(request: Request) -> Response:
        return Response(request.scope["key"])

    routes.add("/", view)
    client = test_client_factory(middleware=[Middleware(TestMiddleware)], routes=routes)

    assert client.get("/").text == "value"
