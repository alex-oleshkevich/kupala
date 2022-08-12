import pytest
import typing
from imia import BearerAuthenticator, InMemoryProvider

from kupala.authentication import BaseUser
from kupala.http.dispatching import route
from kupala.http.exceptions import NotAuthenticated, PageNotFound, PermissionDenied
from kupala.http.guards import has_permission, is_authenticated
from kupala.http.middleware import AuthenticationMiddleware, Middleware
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Routes
from tests.conftest import TestClientFactory


class User(BaseUser):
    def get_id(self) -> typing.Any:
        pass

    def get_display_name(self) -> str:
        pass

    def get_hashed_password(self) -> str:
        pass

    def get_scopes(self) -> list[str]:
        return ["users.edit"]


provider = InMemoryProvider({"1": User()})


def sync_guard(request: Request) -> bool:
    return False


async def async_guard(request: Request) -> bool:
    return False


def exception_guard(request: Request) -> None:
    raise PageNotFound()


def test_sync_guards(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(guards=[sync_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    with pytest.raises(PermissionDenied):
        client.get("/")


def test_async_guards(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(guards=[async_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    with pytest.raises(PermissionDenied):
        client.get("/")


def test_exception_guards(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(guards=[exception_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view)
    client = test_client_factory(routes=routes)

    with pytest.raises(PageNotFound):
        client.get("/")


def test_is_authenticated_guard_allows(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(guards=[is_authenticated])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view)
    client = test_client_factory(
        routes=routes,
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[BearerAuthenticator(user_provider=provider)]),
        ],
    )

    response = client.get("/", headers={"Authorization": "Bearer 1"})
    assert response.status_code == 200


def test_is_authenticated_guard_denies(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(guards=[is_authenticated])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view)
    client = test_client_factory(
        routes=routes,
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[]),
        ],
    )

    with pytest.raises(NotAuthenticated):
        client.get("/")


def test_has_permission_guard_allows(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(guards=[has_permission("users.edit")])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view)
    client = test_client_factory(
        routes=routes,
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[BearerAuthenticator(user_provider=provider)]),
        ],
    )
    response = client.get("/", headers={"Authorization": "Bearer 1"})
    assert response.status_code == 200


def test_has_permission_guard_denies(test_client_factory: TestClientFactory, routes: Routes) -> None:
    @route(guards=[has_permission("users.edit")])
    def view() -> JSONResponse:
        return JSONResponse({})

    routes.add("/", view)
    client = test_client_factory(
        routes=routes,
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[]),
        ],
    )

    with pytest.raises(PermissionDenied):
        client.get("/")
