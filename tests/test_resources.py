from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Router, Routes
from kupala.testclient import TestClient


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


def test_resource_views() -> None:
    app = Kupala()
    app.routes.resource('/users', ExampleResource())
    client = TestClient(app)
    assert client.get('/users').status_code == 200
    assert client.get('/users').text == 'index'

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


def test_resource_partial_views_with_only() -> None:
    app = Kupala()
    app.routes.resource('/users', PartialExampleResource(), only=['index', 'show'])
    client = TestClient(app)
    assert client.get('/users').text == 'index'
    assert client.get('/users/1').text == 'show'
    assert client.post('/users').status_code == 405
    assert client.post('/users/1').status_code == 405


def test_resource_partial_views_with_exclude() -> None:
    app = Kupala()
    app.routes.resource('/users', PartialExampleResource(), exclude=['create', 'update'])
    client = TestClient(app)
    assert client.get('/users').text == 'index'
    assert client.get('/users/1').text == 'show'
    assert client.post('/users').status_code == 405
    assert client.post('/users/1').status_code == 405
