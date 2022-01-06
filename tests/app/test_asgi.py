import typing
from contextlib import asynccontextmanager
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.responses import Response
from kupala.testclient import TestClient
from tests.conftest import TestApp, TestAppFactory


def test_routes(test_app_factory: TestAppFactory) -> None:
    def view() -> Response:
        return Response('ok')

    app = test_app_factory()
    app.routes.add('/', view)

    client = TestClient(app.create_asgi_app())
    assert client.get('/').text == 'ok'


def test_middleware(test_app_factory: TestAppFactory) -> None:
    class TestMiddleware:
        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            scope['key'] = 'value'
            await self.app(scope, receive, send)

    def view(request: Request) -> Response:
        return Response(request.scope['key'])

    app = test_app_factory(middleware=[Middleware(TestMiddleware)])
    app.routes.add('/', view)

    client = TestClient(app.create_asgi_app())
    assert client.get('/').text == 'value'


def test_error_handlers(test_app_factory: TestAppFactory) -> None:
    def on_type_error(request: Request, exc: Exception) -> Response:
        return Response('error')

    def view() -> Response:
        raise TypeError()

    app = test_app_factory(error_handlers={TypeError: on_type_error})
    app.routes.add('/', view)

    client = TestClient(app.create_asgi_app())
    assert client.get('/').text == 'error'


def test_exception_handler(test_app_factory: TestAppFactory) -> None:
    async def on_type_error(request: Request, exc: Exception) -> Response:
        return Response('error')

    def view() -> Response:
        raise TypeError()

    app = test_app_factory(exception_handler=on_type_error, debug=False)
    app.routes.add('/', view)

    client = TestClient(app.create_asgi_app(), raise_server_exceptions=False)
    assert client.get('/').text == 'error'


def test_lifespan(test_app_factory: TestAppFactory) -> None:
    enter_called = False
    exit_called = False

    @asynccontextmanager
    async def handler(app: TestApp) -> typing.AsyncIterator[None]:
        nonlocal enter_called, exit_called
        enter_called = True
        yield
        exit_called = True

    def view() -> Response:
        return Response('content')

    app = test_app_factory(lifespan_handlers=[handler])
    app.routes.add('/', view)

    with TestClient(app.create_asgi_app()) as client:
        client.get('/')
        assert not exit_called
    assert enter_called
    assert exit_called
