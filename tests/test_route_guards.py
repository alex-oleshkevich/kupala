import typing
from imia import BearerAuthenticator, InMemoryProvider

from kupala.application import Kupala
from kupala.authentication import BaseUser
from kupala.http.dispatching import route
from kupala.http.exceptions import PageNotFound
from kupala.http.guards import has_permission, is_authenticated
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Route
from kupala.middleware import Middleware
from kupala.middleware.authentication import AuthenticationMiddleware
from kupala.testclient import TestClient


class User(BaseUser):
    def get_id(self) -> typing.Any:
        pass

    def get_display_name(self) -> str:
        pass

    def get_hashed_password(self) -> str:
        pass

    def get_scopes(self) -> list[str]:
        return ['users.edit']


provider = InMemoryProvider({'1': User()})


def sync_guard(request: Request) -> bool:
    return False


async def async_guard(request: Request) -> bool:
    return False


def exception_guard(request: Request) -> None:
    raise PageNotFound()


def test_sync_guards() -> None:
    @route(guards=[sync_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 403


def test_async_guards() -> None:
    @route(guards=[async_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 403


def test_exception_guards() -> None:
    @route(guards=[exception_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 404


def test_is_authenticated_guard_allows() -> None:
    @route(guards=[is_authenticated])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(
        routes=[Route("/", view)],
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[BearerAuthenticator(user_provider=provider)]),
        ],
    )
    client = TestClient(app)

    response = client.get("/", headers={'Authorization': 'Bearer 1'})
    assert response.status_code == 200


def test_is_authenticated_guard_denies() -> None:
    @route(guards=[is_authenticated])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(
        routes=[Route("/", view)],
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[]),
        ],
    )
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 401


def test_has_permission_guard_allows() -> None:
    @route(guards=[has_permission('users.edit')])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(
        routes=[Route("/", view)],
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[BearerAuthenticator(user_provider=provider)]),
        ],
    )
    client = TestClient(app)
    response = client.get("/", headers={'Authorization': 'Bearer 1'})
    assert response.status_code == 200


def test_has_permission_guard_denies() -> None:
    @route(guards=[has_permission('users.edit')])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(
        routes=[Route("/", view)],
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[]),
        ],
    )
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 403
