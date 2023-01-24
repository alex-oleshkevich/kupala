import datetime
import http.cookies
import itsdangerous
import pytest
import time
from starlette.authentication import AuthCredentials, AuthenticationBackend, BaseUser
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send
from starsessions import CookieStore, SessionMiddleware as StarsessionSessionMiddleware, load_session
from unittest import mock

from kupala.authentication import (
    REMEMBER_COOKIE_NAME,
    SESSION_KEY,
    ChoiceBackend,
    LoginScopes,
    RememberMeBackend,
    SessionBackend,
    confirm_login,
    forget_me,
    is_authenticated,
    login,
    logout,
    remember_me,
)
from tests.conftest import ClientFactory, User


class _DummyBackend(AuthenticationBackend):
    def __init__(self, user: BaseUser | None) -> None:
        self.user = user

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        if self.user:
            return AuthCredentials(), self.user
        return None


@pytest.mark.asyncio
async def test_choice_backend(test_client_factory: ClientFactory, user: User) -> None:
    backend = ChoiceBackend(
        [
            _DummyBackend(None),
            _DummyBackend(None),
        ]
    )
    conn = HTTPConnection({"type": "http"})
    assert await backend.authenticate(conn) is None

    backend = ChoiceBackend(
        [
            _DummyBackend(None),
            _DummyBackend(user),
        ]
    )
    conn = HTTPConnection({"type": "http"})
    result = await backend.authenticate(conn)
    assert result
    _, auth_user = result
    assert auth_user == user


@pytest.mark.asyncio
async def test_session_backend(test_client_factory: ClientFactory, user: User) -> None:
    async def user_loader(conn: HTTPConnection, user_id: str) -> BaseUser | None:
        return user if user_id == user.identity else None

    backend = SessionBackend(user_loader=user_loader)
    conn = HTTPConnection({"type": "http"})
    conn.scope["session"] = {}
    conn.session[SESSION_KEY] = "root"
    result = await backend.authenticate(conn)
    assert result
    _, auth_user = result
    assert auth_user == user

    conn.session[SESSION_KEY] = ""
    assert not await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_session_backend_extracts_user_scopes(test_client_factory: ClientFactory, user: User) -> None:
    class UserWithScopes(User):
        def get_scopes(self) -> list[str]:
            return ["admin"]

    async def user_loader(conn: HTTPConnection, user_id: str) -> BaseUser | None:
        return UserWithScopes(username="test")

    backend = SessionBackend(user_loader=user_loader)
    conn = HTTPConnection({"type": "http"})
    conn.scope["session"] = {}
    conn.session[SESSION_KEY] = "root"
    result = await backend.authenticate(conn)
    assert result
    assert result[0].scopes == ["admin"]


@pytest.mark.asyncio
async def test_remember_me_backend(test_client_factory: ClientFactory, user: User) -> None:
    async def user_loader(conn: HTTPConnection, user_id: str) -> BaseUser | None:
        return user if user_id == user.identity else None

    secret_key = "key!"
    backend = RememberMeBackend(user_loader=user_loader, secret_key=secret_key)
    conn = HTTPConnection({"type": "http", "headers": {}})
    conn.cookies[REMEMBER_COOKIE_NAME] = itsdangerous.TimestampSigner(secret_key=secret_key).sign("root").decode()
    result = await backend.authenticate(conn)
    assert result
    auth_credentials, auth_user = result
    assert auth_user == user
    assert "login:remembered" in auth_credentials.scopes


@pytest.mark.asyncio
async def test_remember_me_backend_not_authenticates(test_client_factory: ClientFactory, user: User) -> None:
    async def user_loader(conn: HTTPConnection, user_id: str) -> BaseUser | None:
        return None

    secret_key = "key!"
    backend = RememberMeBackend(user_loader=user_loader, secret_key=secret_key)
    conn = HTTPConnection({"type": "http", "headers": {}})
    conn.cookies[REMEMBER_COOKIE_NAME] = itsdangerous.TimestampSigner(secret_key=secret_key).sign("root").decode()
    assert not await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_remember_me_backend_checks_max_age(test_client_factory: ClientFactory, user: User) -> None:
    async def user_loader(conn: HTTPConnection, user_id: str) -> BaseUser | None:
        return user if user_id == user.identity else None

    secret_key = "key!"
    backend = RememberMeBackend(user_loader=user_loader, secret_key=secret_key, duration=datetime.timedelta(seconds=20))
    conn = HTTPConnection({"type": "http", "headers": {}})
    ts = time.time()

    # cookie generated 10 seconds ago
    # remember me lifetime = 20 seconds
    # test must pass
    with mock.patch("itsdangerous.TimestampSigner.get_timestamp", return_value=int(ts - 10)):
        conn.cookies[REMEMBER_COOKIE_NAME] = itsdangerous.TimestampSigner(secret_key=secret_key).sign("root").decode()
        result = await backend.authenticate(conn)
        assert result
        auth_credentials, auth_user = result
        assert auth_user == user

    # cookie generated 30 seconds ago
    # remember me lifetime = 20 seconds
    # test must fail
    with mock.patch("itsdangerous.TimestampSigner.get_timestamp", return_value=int(ts - 30)):
        conn.cookies[REMEMBER_COOKIE_NAME] = itsdangerous.TimestampSigner(secret_key=secret_key).sign("root").decode()
    assert not await backend.authenticate(conn)


def test_login() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        user = User(username="root")
        await login(request, user)
        authenticated = is_authenticated(request)
        await Response("yes" if authenticated else "no")(scope, receive, send)

    client = TestClient(SessionMiddleware(app, secret_key="key!"))
    response = client.get("/")
    assert response.text == "yes"
    assert "session" in response.cookies


def test_login_regenerates_session_id() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        await load_session(request)
        user = User(username="root")
        await login(request, user)
        authenticated = is_authenticated(request)
        await Response("yes" if authenticated else "no")(scope, receive, send)

    with mock.patch("starsessions.regenerate_session_id") as fn:
        client = TestClient(StarsessionSessionMiddleware(app, store=CookieStore(secret_key="key!")))
        client.get("/")
        fn.assert_called_once()


def test_logout() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        user = User(username="root")
        await login(request, user)
        assert is_authenticated(request)

        await logout(request)
        await Response("yes" if request.user.is_authenticated else "no")(scope, receive, send)

    client = TestClient(SessionMiddleware(app, secret_key="key!"))
    response = client.get("/")
    assert response.text == "no"
    assert "session" not in response.cookies


def test_confirm_logins() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        user = User(username="root")
        await login(request, user)
        request.auth.scopes.append(LoginScopes.REMEMBERED)
        confirm_login(request)

        is_fresh = LoginScopes.REMEMBERED not in request.auth.scopes
        await Response("yes" if is_fresh else "no")(scope, receive, send)

    client = TestClient(SessionMiddleware(app, secret_key="key!"))
    assert client.get("/").text == "yes"


def test_remember_me(user: User) -> None:
    response = Response()
    remember_me(response, "key!", user, duration=datetime.timedelta(seconds=10))
    cookies: http.cookies.SimpleCookie = http.cookies.SimpleCookie(response.headers["set-cookie"])
    assert REMEMBER_COOKIE_NAME in cookies
    assert cookies[REMEMBER_COOKIE_NAME]["max-age"] == "10"

    response = Response()
    forget_me(response)
    cookies = http.cookies.SimpleCookie(response.headers["set-cookie"])
    assert REMEMBER_COOKIE_NAME in cookies
    assert cookies[REMEMBER_COOKIE_NAME]["max-age"] == "-1"
