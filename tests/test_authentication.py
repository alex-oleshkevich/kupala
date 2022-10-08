import dataclasses

import datetime
from itsdangerous import Signer
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send
from unittest import mock

from kupala.authentication import (
    AnonymousUser,
    AuthenticationMiddleware,
    AuthToken,
    LoginState,
    RememberMeAuthenticator,
    SessionAuthenticator,
    UserLike,
    confirm_login,
    is_authenticated,
    login,
    logout,
    remember_me,
)
from kupala.http import Request, Response
from kupala.testclient import TestClient


@dataclasses.dataclass
class User(UserLike):
    id: str

    def get_id(self) -> str:
        return self.id

    def __str__(self) -> str:
        return self.id


def test_login() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        user = User(id="id")
        await login(request, user)
        authenticated = is_authenticated(request)
        await Response("yes" if authenticated else "no")(scope, receive, send)

    client = TestClient(SessionMiddleware(app, secret_key="key!"))
    response = client.get("/")
    assert response.text == "yes"
    assert "session" in response.cookies


def test_logout() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        user = User(id="id")
        await login(request, user)
        assert is_authenticated(request)

        await logout(request)
        await Response("yes" if request.auth else "no")(scope, receive, send)

    client = TestClient(SessionMiddleware(app, secret_key="key!"))
    response = client.get("/")
    assert response.text == "no"
    assert "session" not in response.cookies


def test_confirm_logins() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        user = User(id="id")
        await login(request, user)
        request.auth.change_state(LoginState.REMEMBERED)
        confirm_login(request)

        await Response(request.auth.state)(scope, receive, send)

    client = TestClient(SessionMiddleware(app, secret_key="key!"))
    assert client.get("/").text == "fresh"


@mock.patch("time.time", lambda: 0)
def test_remember_me_set_cookie() -> None:
    @dataclasses.dataclass
    class AppLike:
        secret_key: str

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = AppLike(secret_key="key!")
        request = Request(scope, receive, send)
        user = User(id="id")
        await login(request, user)
        response = Response("ok")
        remember_me(request, response, user, datetime.timedelta(hours=24))
        await response(scope, receive, send)

    client = TestClient(SessionMiddleware(app, secret_key="key!"))
    response = client.get("/")
    assert "remember_me" in response.cookies


def test_middleware_authenticates_via_session() -> None:
    users = {"id": User(id="id")}

    async def user_loader(connection: HTTPConnection, user_id: str) -> UserLike | None:
        return users.get(user_id)

    def init_session(app: ASGIApp) -> ASGIApp:
        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive, send)
            request.session["__user_id__"] = "id"
            await app(scope, receive, send)

        return inner

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response = Response("yes" if request.auth.is_authenticated else "no")
        await response(scope, receive, send)

    client = TestClient(
        SessionMiddleware(
            init_session(
                AuthenticationMiddleware(
                    app,
                    authenticators=[SessionAuthenticator(user_loader=user_loader)],
                ),
            ),
            secret_key="key!",
        ),
    )
    assert client.get("/").text == "yes"


def test_middleware_not_authenticates_invalid_users_via_session() -> None:
    users = {"other": User(id="other")}

    async def user_loader(connection: HTTPConnection, user_id: str) -> UserLike | None:
        return users.get(user_id)

    def init_session(app: ASGIApp) -> ASGIApp:
        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive, send)
            request.session["__user_id__"] = "id"
            await app(scope, receive, send)

        return inner

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response = Response("yes" if request.auth.is_authenticated else "no")
        await response(scope, receive, send)

    client = TestClient(
        SessionMiddleware(
            init_session(
                AuthenticationMiddleware(
                    app,
                    authenticators=[SessionAuthenticator(user_loader=user_loader)],
                ),
            ),
            secret_key="key!",
        ),
    )
    assert client.get("/").text == "no"


def test_middleware_authenticates_via_remember_me() -> None:
    users = {"id": User(id="id")}

    @dataclasses.dataclass
    class AppLike:
        secret_key: str

    async def user_loader(_: HTTPConnection, user_id: str) -> UserLike | None:
        return users.get(user_id)

    def init_app(app: ASGIApp) -> ASGIApp:
        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            scope["app"] = AppLike(secret_key="key!")
            await app(scope, receive, send)

        return inner

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response = Response("yes" if request.auth.is_authenticated else "no")
        await response(scope, receive, send)

    client = TestClient(
        init_app(
            SessionMiddleware(
                AuthenticationMiddleware(
                    app,
                    authenticators=[RememberMeAuthenticator(user_loader=user_loader)],
                ),
                secret_key="key!",
            ),
        ),
    )

    signer = Signer("key!")
    assert client.get("/", cookies={"remember_me": signer.sign("id").decode()}).text == "yes"


def test_middleware_not_authenticates_invalid_users_via_remember_me() -> None:
    users = {"other": User(id="other")}

    @dataclasses.dataclass
    class AppLike:
        secret_key: str

    async def user_loader(_: HTTPConnection, user_id: str) -> UserLike | None:
        return users.get(user_id)

    def init_app(app: ASGIApp) -> ASGIApp:
        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            scope["app"] = AppLike(secret_key="key!")
            await app(scope, receive, send)

        return inner

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response = Response("yes" if request.auth.is_authenticated else "no")
        await response(scope, receive, send)

    client = TestClient(
        init_app(
            SessionMiddleware(
                AuthenticationMiddleware(
                    app,
                    authenticators=[RememberMeAuthenticator(user_loader=user_loader)],
                ),
                secret_key="key!",
            ),
        ),
    )

    signer = Signer("key!")
    assert client.get("/", cookies={"remember_me": signer.sign("id").decode()}).text == "no"


def test_middleware_remember_me_not_fails_on_tampered_cookie() -> None:
    users = {"id": User(id="id")}

    @dataclasses.dataclass
    class AppLike:
        secret_key: str

    async def user_loader(_: HTTPConnection, user_id: str) -> UserLike | None:
        return users.get(user_id)

    def init_app(app: ASGIApp) -> ASGIApp:
        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            scope["app"] = AppLike(secret_key="key!")
            await app(scope, receive, send)

        return inner

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response = Response("yes" if request.auth.is_authenticated else "no")
        await response(scope, receive, send)

    client = TestClient(
        init_app(
            SessionMiddleware(
                AuthenticationMiddleware(
                    app,
                    authenticators=[RememberMeAuthenticator(user_loader=user_loader)],
                ),
                secret_key="key!",
            ),
        ),
    )

    assert client.get("/", cookies={"remember_me": "bad cookie"}).text == "no"


def test_middleware_on_success() -> None:
    users = {"id": User(id="id")}

    async def user_loader(_: HTTPConnection, user_id: str) -> UserLike | None:
        return users.get(user_id)

    def init_session(app: ASGIApp) -> ASGIApp:
        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive, send)
            request.session["__user_id__"] = "id"
            await app(scope, receive, send)

        return inner

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response = Response("yes" if request.auth.is_authenticated else "no")
        await response(scope, receive, send)

    spy = mock.AsyncMock()

    client = TestClient(
        SessionMiddleware(
            init_session(
                AuthenticationMiddleware(
                    app, authenticators=[SessionAuthenticator(user_loader=user_loader)], on_success=spy
                ),
            ),
            secret_key="key!",
        ),
    )
    assert client.get("/").text == "yes"
    spy.assert_called_once()


def test_anonymous_user() -> None:
    user = AnonymousUser()
    assert user.get_id() == ""
    assert str(user) == "Anonymous"


def test_auth_token() -> None:
    user = User(id="root")
    token = AuthToken(user=user, state=LoginState.FRESH, scopes=["admin"])
    assert token.id == "root"
    assert token.is_authenticated is True
    assert token.is_anonymous is False
    assert token.is_fresh is True
    assert token.is_remembered is False
    assert token.state == LoginState.FRESH
    assert token.scopes == ["admin"]
    assert bool(token) is True
    assert str(token) == "root"
    assert repr(token) == "<AuthToken: state=fresh, user=root>"
    assert "admin" in token

    token.change_state(LoginState.ANONYMOUS)
    assert token.is_anonymous is True
    assert token.is_authenticated is False

    token.change_state(LoginState.REMEMBERED)
    assert token.is_remembered is True
    assert token.is_fresh is False
