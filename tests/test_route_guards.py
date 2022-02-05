from starsessions import SessionMiddleware

from kupala.application import Kupala
from kupala.dispatching import action_config
from kupala.exceptions import PageNotFound
from kupala.guards import is_authenticated
from kupala.middleware import Middleware
from kupala.middleware.authentication import AuthenticationMiddleware
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.routing import Route
from kupala.testclient import TestClient


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


def test_is_authenticated_guard() -> None:
    @action_config(guards=[is_authenticated])
    def view() -> JSONResponse:
        return JSONResponse({})

    app = Kupala(
        routes=[Route("/", view)],
        middleware=[
            Middleware(SessionMiddleware, secret_key='key'),
            Middleware(AuthenticationMiddleware, authenticators=[]),
        ],
    )
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 403
