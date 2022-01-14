from starlette.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.application import Kupala
from kupala.dispatching import action_config
from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.routing import Route
from tests.utils import FormatRenderer


@action_config()
async def action_config_view(request: Request) -> JSONResponse:
    return JSONResponse({'method': request.method})


@action_config(['get', 'post'])
async def action_config_methods_view(request: Request) -> JSONResponse:
    return JSONResponse({'method': request.method})


class SampleMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope['called'] = True
        return await self.app(scope, receive, send)


@action_config(middleware=[Middleware(SampleMiddleware)])
async def action_config_middleware_view(request: Request) -> JSONResponse:
    return JSONResponse({'called': request.scope['called']})


@action_config(template='hello %(name)s')
async def action_config_template_view() -> dict:
    return {'name': 'world'}


app = Kupala(
    routes=[
        Route("/action-config", action_config_view),
        Route("/action-config-methods", action_config_methods_view),
        Route("/action-config-middleware", action_config_middleware_view),
        Route("/action-config-template", action_config_template_view),
    ],
    renderer=FormatRenderer(),
)
client = TestClient(app)


def test_action_config() -> None:
    response = client.get("/action-config")
    assert response.json() == {'method': 'GET'}


def test_action_config_methods() -> None:
    response = client.get("/action-config-methods")
    assert response.json() == {'method': 'GET'}

    response = client.post("/action-config-methods")
    assert response.json() == {'method': 'POST'}


def test_action_config_middleware() -> None:
    response = client.get("/action-config-middleware")
    assert response.json() == {'called': True}


def test_action_config_template() -> None:
    response = client.get("/action-config-template", headers={'accept': 'text/html'})
    assert response.text == 'hello world'


def test_action_config_overrides_methods() -> None:
    """Methods defined by action_config() have higher precedence."""

    @action_config(methods=['post'])
    def view() -> dict:
        return {}

    app = Kupala()
    app.routes.add('/', view, methods=['get'])
    client = TestClient(app)
    assert client.get('/').status_code == 405
    assert client.post('/').status_code == 200


def test_action_config_overrides_middleware() -> None:
    """Methods defined by action_config() have higher precedence."""

    def set_one(app: ASGIApp) -> ASGIApp:
        async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
            scope['used'] = 'one'
            await app(scope, receive, send)

        return middleware

    def set_two(app: ASGIApp) -> ASGIApp:
        async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
            scope['used'] = 'two'
            await app(scope, receive, send)

        return middleware

    @action_config(middleware=[Middleware(set_two)])
    def view(request: Request) -> str:
        return request.scope['used']

    app = Kupala()
    app.routes.add('/', view, middleware=[Middleware(set_one)])
    client = TestClient(app)
    assert client.get('/').text == 'two'
