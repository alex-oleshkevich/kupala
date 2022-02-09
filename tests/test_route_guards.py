import typing
from imia import BearerAuthenticator, InMemoryProvider

from kupala.application import Kupala
from kupala.authentication import BaseUser
from kupala.dispatching import action_config
from kupala.exceptions import PageNotFound
from kupala.guards import has_permission, is_authenticated
from kupala.middleware import Middleware
from kupala.middleware.authentication import AuthenticationMiddleware
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.routing import Route
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
    @action_config(guards=[sync_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 403


def test_async_guards() -> None:
    @action_config(guards=[async_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 403


def test_exception_guards() -> None:
    @action_config(guards=[exception_guard])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(routes=[Route("/", view)])
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 404


def test_is_authenticated_guard_allows() -> None:
    @action_config(guards=[is_authenticated])
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
    @action_config(guards=[is_authenticated])
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
    @action_config(guards=[has_permission('users.edit')])
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
    @action_config(guards=[has_permission('users.edit')])
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
