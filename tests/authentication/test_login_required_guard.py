from starlette.authentication import AuthCredentials, AuthenticationBackend, BaseUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response

from kupala.authentication import login_required
from kupala.routing import route
from tests.conftest import ClientFactory, User


class _DummyLoginBackend(AuthenticationBackend):
    def __init__(self, user: User) -> None:
        self.user = user

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        if "login" in conn.query_params:
            return AuthCredentials(), self.user
        return None


def test_login_required_guard_redirects_to_url(test_client_factory: ClientFactory, user: User) -> None:
    @route("/", guards=[login_required("/login")])
    def view(request: Request) -> None:  # pragma: nocover
        ...

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=_DummyLoginBackend(user)),
        ],
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=%2F"


def test_login_required_guard_redirects_to_path(test_client_factory: ClientFactory, user: User) -> None:
    @route("/", guards=[login_required(path_name="login", path_params={"id": 1})])
    def view(request: Request) -> None:  # pragma: nocover
        ...

    @route("/security/login/{id}", name="login")
    def login_view(request: Request) -> None:  # pragma: nocover
        ...

    client = test_client_factory(
        routes=[view, login_view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=_DummyLoginBackend(user)),
        ],
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "http://testserver/security/login/1?next=%2F"


def test_login_required_guard_redirects_to_default_route_path(test_client_factory: ClientFactory, user: User) -> None:
    @route("/", guards=[login_required()])
    def view(request: Request) -> None:  # pragma: nocover
        ...

    @route("/security/login", name="login")
    def login_view(request: Request) -> None:  # pragma: nocover
        ...

    client = test_client_factory(
        routes=[view, login_view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=_DummyLoginBackend(user)),
        ],
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "http://testserver/security/login?next=%2F"


def test_login_required_guard_grants_access(test_client_factory: ClientFactory, user: User) -> None:
    @route("/", guards=[login_required()])
    def view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=_DummyLoginBackend(user)),
        ],
    )
    response = client.get("/?login", follow_redirects=False)
    assert response.status_code == 200
