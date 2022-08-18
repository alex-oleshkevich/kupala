import pytest
import typing
from imia import BearerAuthenticator, InMemoryProvider
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.authentication import BaseUser
from kupala.http import NotAuthenticated, PermissionDenied
from kupala.http.dispatching import route
from kupala.http.middleware import AuthenticationMiddleware, Middleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Routes
from tests.conftest import TestClientFactory


class SampleMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["called"] = True
        return await self.app(scope, receive, send)


def test_action_config(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route()
    async def view(request: Request) -> JSONResponse:
        return JSONResponse({"method": request.method})

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    response = client.get("/")
    assert response.json() == {"method": "GET"}


def test_action_config_methods(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(["get", "post"])
    async def view(request: Request) -> JSONResponse:
        return JSONResponse({"method": request.method})

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    response = client.get("/")
    assert response.json() == {"method": "GET"}

    response = client.post("/")
    assert response.json() == {"method": "POST"}


def test_route_overrides_action_config_methods(test_client_factory: TestClientFactory, routes: Routes) -> None:
    """Methods defined by action_config() have higher precedence."""

    @route(methods=["post"])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view, methods=["get"])
    client = test_client_factory(routes=routes)
    assert client.get("/").status_code == 200
    with pytest.raises(HTTPException):
        assert client.post("/").status_code == 405


def test_view_allows_unauthenticated_access(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(is_authenticated=False)
    def view() -> JSONResponse:
        return JSONResponse([])

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    assert client.get("/").status_code == 200


def test_when_view_requires_authentication_authenticated_user_can_access_page(
    test_client_factory: TestClientFactory, routes: Routes
) -> None:
    @route(is_authenticated=True)
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

    user_provider = InMemoryProvider({"root": User()})
    routes.add("/", view)
    client = test_client_factory(
        routes=routes,
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[BearerAuthenticator(user_provider)]),
        ],
    )

    assert client.get("/", headers={"authorization": "Bearer root"}).status_code == 200


def test_when_view_requires_authentication_unauthenticated_user_cannoe_access_page(
    test_client_factory: TestClientFactory, routes: Routes
) -> None:
    @route(is_authenticated=True)
    def view() -> JSONResponse:
        return JSONResponse([])

    user_provider = InMemoryProvider({})
    routes.add("/", view)
    client = test_client_factory(
        routes=routes,
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[BearerAuthenticator(user_provider)]),
        ],
    )
    with pytest.raises(NotAuthenticated):
        assert client.get("/").status_code == 401


def test_access_when_user_has_permission(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(permission="admin")
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

    user_provider = InMemoryProvider({"admin": User(scopes=["admin"]), "user": User(scopes=["user"])})
    routes.add("/", view)
    client = test_client_factory(
        routes=routes,
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[BearerAuthenticator(user_provider)]),
        ],
    )

    assert client.get("/", headers={"authorization": "Bearer admin"}).status_code == 200
    with pytest.raises(PermissionDenied):
        assert client.get("/", headers={"authorization": "Bearer user"}).status_code == 403
