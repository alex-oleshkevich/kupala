import typing
from imia import BearerAuthenticator, InMemoryProvider
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.application import Kupala
from kupala.authentication import BaseUser
from kupala.dispatching import action_config
from kupala.middleware import Middleware
from kupala.middleware.authentication import AuthenticationMiddleware
from kupala.requests import Request
from kupala.responses import JSONResponse, PlainTextResponse
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


app = Kupala(
    routes=[
        Route("/action-config", action_config_view),
        Route("/action-config-methods", action_config_methods_view),
        Route("/action-config-middleware", action_config_middleware_view),
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


def test_route_overrides_action_config_methods() -> None:
    """Methods defined by action_config() have higher precedence."""

    @action_config(methods=['post'])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala()
    app.routes.add('/', view, methods=['get'])
    client = TestClient(app)
    assert client.get('/').status_code == 200
    assert client.post('/').status_code == 405


def test_route_overrides_action_config_middleware() -> None:
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
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.scope['used'])

    app = Kupala()
    app.routes.add('/', view, middleware=[Middleware(set_one)])
    client = TestClient(app)
    assert client.get('/').text == 'one'


def test_view_allows_unauthenticated_access() -> None:
    @action_config(is_authenticated=False)
    def view() -> JSONResponse:
        return JSONResponse([])

    app = Kupala(routes=[Route('/', view)])
    client = TestClient(app)
    assert client.get('/').status_code == 200


def test_when_view_requires_authentication_authenticated_user_can_access_page() -> None:
    @action_config(is_authenticated=True)
    def view() -> JSONResponse:
        return JSONResponse([])

    class User(BaseUser):
        def get_id(self) -> typing.Any:
            pass

        def get_display_name(self) -> str:
            pass

        def get_scopes(self) -> list[str]:
            pass

        def get_hashed_password(self) -> str:
            pass

    user_provider = InMemoryProvider({'root': User()})
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[
            AuthenticationMiddleware.configure(authenticators=[BearerAuthenticator(user_provider)]),
        ],
    )
    client = TestClient(app)
    assert client.get('/', headers={'authorization': 'Bearer root'}).status_code == 200


def test_when_view_requires_authentication_unauthenticated_user_cannoe_access_page() -> None:
    @action_config(is_authenticated=True)
    def view() -> JSONResponse:
        return JSONResponse([])

    user_provider = InMemoryProvider({})
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[
            AuthenticationMiddleware.configure(authenticators=[BearerAuthenticator(user_provider)]),
        ],
    )
    client = TestClient(app)
    assert client.get('/').status_code == 401


def test_access_when_user_has_permission() -> None:
    @action_config(permission='admin')
    def view() -> JSONResponse:
        return JSONResponse([])

    class User(BaseUser):
        def __init__(self, scopes: list[str]) -> None:
            self.scopes = scopes

        def get_id(self) -> typing.Any:
            pass

        def get_display_name(self) -> str:
            pass

        def get_scopes(self) -> list[str]:
            return self.scopes

        def get_hashed_password(self) -> str:
            pass

    user_provider = InMemoryProvider({'admin': User(scopes=['admin']), 'user': User(scopes=['user'])})
    app = Kupala(
        routes=[Route('/', view)],
        middleware=[
            AuthenticationMiddleware.configure(authenticators=[BearerAuthenticator(user_provider)]),
        ],
    )
    client = TestClient(app)
    assert client.get('/', headers={'authorization': 'Bearer admin'}).status_code == 200
    assert client.get('/', headers={'authorization': 'Bearer user'}).status_code == 403
