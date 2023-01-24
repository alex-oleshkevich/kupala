import pytest
from starlette.authentication import AuthCredentials, AuthenticationBackend, BaseUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.types import Message
from unittest import mock

from kupala.authentication import LoginRequiredMiddleware
from kupala.routing import route
from tests.conftest import ClientFactory, User


class _DummyLoginBackend(AuthenticationBackend):
    def __init__(self, user: User) -> None:
        self.user = user

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        return (AuthCredentials(), self.user) if "login" in conn.query_params else None


def test_login_required_middleware_redirects_to_url(test_client_factory: ClientFactory, user: User) -> None:
    @route("/")
    def view(request: Request) -> None:  # pragma: nocover
        ...

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=_DummyLoginBackend(user)),
            Middleware(LoginRequiredMiddleware, redirect_url="/login"),
        ],
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=%2F"


def test_login_required_middleware_redirects_to_path(test_client_factory: ClientFactory, user: User) -> None:
    @route("/")
    def view(request: Request) -> None:  # pragma: nocover
        ...

    @route("/security/login/{id}", name="login")
    def login_view(request: Request) -> None:  # pragma: nocover
        ...

    client = test_client_factory(
        routes=[view, login_view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=_DummyLoginBackend(user)),
            Middleware(LoginRequiredMiddleware, path_name="login", path_params={"id": "1"}),
        ],
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/security/login/1?next=%2F"


def test_login_required_middleware_redirects_to_default_route_path(
    test_client_factory: ClientFactory, user: User
) -> None:
    @route("/")
    def view(request: Request) -> None:  # pragma: nocover
        ...

    @route("/security/login", name="login")
    def login_view(request: Request) -> None:  # pragma: nocover
        ...

    client = test_client_factory(
        routes=[view, login_view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=_DummyLoginBackend(user)),
            Middleware(LoginRequiredMiddleware),
        ],
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/security/login?next=%2F"


@pytest.mark.asyncio
async def test_login_required_middleware_bypass_unsupported_request_types(
    test_client_factory: ClientFactory, user: User
) -> None:
    async def receive() -> Message:  # pragma: nocover
        return {}

    async def send(message: Message) -> None:  # pragma: nocover
        ...

    base_app = mock.AsyncMock()
    app = LoginRequiredMiddleware(base_app)
    await app({"type": "unsupported"}, receive, send)
    base_app.assert_called_once()


@pytest.mark.asyncio
async def test_login_calls_next_app_on_success(test_client_factory: ClientFactory, user: User) -> None:
    async def receive() -> Message:  # pragma: nocover
        return {}

    async def send(message: Message) -> None:  # pragma: nocover
        ...

    base_app = mock.AsyncMock()
    app = LoginRequiredMiddleware(base_app)
    await app({"type": "http", "user": user}, receive, send)
    base_app.assert_called_once()

    base_app = mock.AsyncMock()
    app = LoginRequiredMiddleware(base_app)
    await app({"type": "websocket", "user": user}, receive, send)
    base_app.assert_called_once()
