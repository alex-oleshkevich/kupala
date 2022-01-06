import typing as t
from starlette.types import ASGIApp, Receive, Scope, Send
from unittest import mock

from kupala.application import Kupala
from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.resources import action
from kupala.responses import JSONResponse, Response
from kupala.routing import Router, Routes
from kupala.testclient import TestClient


class ExampleMiddleware:
    def __init__(self, app: ASGIApp, callback: t.Callable = None) -> None:
        self.app = app
        self.callback = callback

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.callback:
            self.callback()
        scope['example_middleware'] = True
        return await self.app(scope, receive, send)


class _RequestInjection:
    @classmethod
    def from_request(cls, request: Request) -> '_RequestInjection':
        return cls()


class _AppInjection:
    @classmethod
    def from_request(cls, request: Request) -> '_AppInjection':
        return cls()


class ExampleResource:
    async def index(self, request: Request) -> Response:
        return Response('index')

    async def new(self, request: Request) -> Response:
        return Response('new')

    async def create(self, request: Request) -> Response:
        return Response('create')

    async def show(self, request: Request) -> Response:
        return Response('show')

    async def edit(self, request: Request) -> Response:
        return Response('edit')

    async def update(self, request: Request) -> Response:
        return Response('update')

    async def destroy(self, request: Request) -> Response:
        return Response('destroy')

    @action('/export', ['GET', 'POST'], path_name='export')
    async def export(self, request: Request) -> Response:
        return Response('export')

    @action('/activate', ['GET', 'POST'], path_name='activate', scope='object')
    async def activate(self, request: Request) -> Response:
        return Response('activate')

    @action('/middleware', ['GET', 'POST'], path_name='middleware', middleware=[Middleware(ExampleMiddleware)])
    async def middleware(self, request: Request) -> Response:
        return Response('yes' if 'example_middleware' in request.scope else 'no')

    @action('/injections', path_name='injections')
    async def injections(self, from_request: _RequestInjection, from_app: _AppInjection) -> Response:
        return JSONResponse([from_request.__class__.__name__, from_app.__class__.__name__])


def test_resource_views() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource())
    client = TestClient(app)
    assert client.get('/users').status_code == 200
    assert client.get('/users').text == 'index'

    assert client.put('/users').status_code == 405

    assert client.get('/users/new').status_code == 200
    assert client.get('/users/new').text == 'new'

    assert client.post('/users').status_code == 200
    assert client.post('/users').text == 'create'

    assert client.get('/users/1').status_code == 200
    assert client.get('/users/1').text == 'show'

    assert client.get('/users/1/edit').status_code == 200
    assert client.get('/users/1/edit').text == 'edit'

    assert client.put('/users/1').status_code == 200
    assert client.put('/users/1').text == 'update'

    assert client.patch('/users/1').status_code == 200
    assert client.patch('/users/1').text == 'update'

    assert client.delete('/users/1').status_code == 200
    assert client.delete('/users/1').text == 'destroy'

    assert client.request('trace', '/users/1').status_code == 405


def test_resource_url_generation() -> None:
    routes = Routes()
    routes.resource('/users/', ExampleResource(), name='example')

    router = Router(routes)
    assert router.url_path_for('example.list') == '/users'
    assert router.url_path_for('example.new') == '/users/new'
    assert router.url_path_for('example.detail', id='1') == '/users/1'
    assert router.url_path_for('example.edit', id='1') == '/users/1/edit'


class PartialExampleResource:
    async def index(self, request: Request) -> Response:
        return Response('index')

    async def show(self, request: Request) -> Response:
        return Response('show')


def test_partial_resource() -> None:
    app = Kupala()
    app.routes.resource('/users', PartialExampleResource())
    client = TestClient(app)
    assert client.get('/users').text == 'index'
    assert client.get('/users/1').text == 'show'
    assert client.post('/users').status_code == 405
    assert client.post('/users/1').status_code == 405
    assert client.put('/users/1').status_code == 405
    assert client.delete('/users/1').status_code == 405


def test_resource_partial_views_with_only() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource(), only=['index', 'show', 'export'])
    client = TestClient(app)
    assert client.get('/users').text == 'index'
    assert client.get('/users/1').text == 'show'
    assert client.post('/users').status_code == 405
    assert client.post('/users/1').status_code == 405
    assert client.post('/users/export').status_code == 200


def test_resource_partial_views_with_exclude() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource(), exclude=['create', 'update', 'export'])
    client = TestClient(app)
    assert client.get('/users').text == 'index'
    assert client.get('/users/1').text == 'show'
    assert client.post('/users').status_code == 405
    assert client.post('/users/1').status_code == 405

    # here /users/export will be caught by /users/{id} route, so 405 here
    assert client.post('/users/export').status_code == 404


def test_custom_collection_actions() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource())
    client = TestClient(app)
    assert client.post('/users/export').status_code == 200
    assert client.get('/users/export').text == 'export'


def test_custom_object_actions() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource())
    client = TestClient(app)
    assert client.post('/users/1/activate').status_code == 200
    assert client.get('/users/1/activate').text == 'activate'


def test_resource_middleware() -> None:
    spy = mock.MagicMock()

    app = Kupala()
    app.routes.resource('/users', ExampleResource(), middleware=[Middleware(ExampleMiddleware, callback=spy)])
    client = TestClient(app)
    assert client.get('/users/').status_code == 200
    spy.assert_called_once()


def test_custom_resource_action_middleware() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource())
    client = TestClient(app)
    assert client.get('/users/middleware').status_code == 200
    assert client.get('/users/middleware').text == 'yes'


def test_api_resource_route() -> None:
    app = Kupala()
    app.routes.api_resource('/users', ExampleResource())
    client = TestClient(app)
    assert client.get('/users/new').status_code == 404
    assert client.get('/users/1/edit').status_code == 404


class SomeService:
    ...


class InjectionResource:
    async def show(self, id: int) -> JSONResponse:
        return JSONResponse({'id': id})


def test_resource_route_injects_path_params() -> None:
    app = Kupala()
    app.routes.resource('/test', InjectionResource())

    client = TestClient(app)
    response = client.get('/test/2')
    assert response.status_code == 200
    assert response.json() == {'id': 2}


def test_inject_from_request_and_app_view() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource())

    client = TestClient(app)
    response = client.get("/users/injections")
    assert response.status_code == 200
    assert response.json() == ['_RequestInjection', '_AppInjection']
