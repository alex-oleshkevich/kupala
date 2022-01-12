from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.application import Kupala
from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.responses import Response
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


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


class CustomRequest(Request):
    ...


def test_custom_request_class(test_app_factory: TestAppFactory) -> None:
    def view(request: CustomRequest) -> Response:
        return Response(request.__class__.__name__)

    app = test_app_factory(request_class=CustomRequest)
    app.routes.add('/', view)

    client = TestClient(app.create_asgi_app())
    assert client.get('/').text == 'CustomRequest'


def test_custom_request_class_via_class_attribute(test_app_factory: TestAppFactory) -> None:
    class ExampleApp(Kupala):
        request_class = CustomRequest

    def view(request: CustomRequest) -> Response:
        return Response(request.__class__.__name__)

    app = test_app_factory(app_class=ExampleApp)
    app.routes.add('/', view)

    client = TestClient(app.create_asgi_app())
    assert client.get('/').text == 'CustomRequest'
