from __future__ import annotations

import abc
import datetime
import enum
import typing
from itsdangerous import BadSignature, Signer
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.responses import Response

SESSION_KEY = "__user_id__"
REMEMBER_COOKIE_NAME = "remember_me"


class LoginState(str, enum.Enum):
    FRESH = "fresh"
    REMEMBERED = "remembered"
    ANONYMOUS = "anonymous"


class UserLike(abc.ABC):
    def get_id(self) -> str:  # pragma: nocover
        raise NotImplementedError()


class AnonymousUser(UserLike):
    def get_id(self) -> str:
        return ""

    def __str__(self) -> str:
        return "Anonymous"


_T = typing.TypeVar("_T", bound=UserLike)


class AuthToken(typing.Generic[_T]):
    def __init__(self, user: _T, state: LoginState, scopes: list[str] | None = None) -> None:
        self.user = user
        self._state = state
        self._scopes = list(scopes or [])

    @property
    def id(self) -> typing.Any:
        return self.user.get_id()

    @property
    def is_authenticated(self) -> bool:
        return self._state != LoginState.ANONYMOUS

    @property
    def is_anonymous(self) -> bool:
        return self._state == LoginState.ANONYMOUS

    @property
    def is_fresh(self) -> bool:
        return self._state == LoginState.FRESH

    @property
    def is_remembered(self) -> bool:
        return self._state == LoginState.REMEMBERED

    @property
    def state(self) -> LoginState:
        return self._state

    @property
    def scopes(self) -> list[str]:
        return self._scopes

    def change_state(self, new_state: LoginState) -> AuthToken:
        self._state = new_state
        return self

    def __bool__(self) -> bool:
        return self.is_authenticated

    def __str__(self) -> str:
        return str(self.user)

    def __contains__(self, requirement: str) -> bool:
        return requirement in self.scopes

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: state={self.state}, user={self.user}>"


class Authenticator(typing.Protocol):  # pragma: nocover
    async def __call__(self, connection: HTTPConnection) -> AuthToken | None:
        ...


ByIdUserFinder = typing.Callable[[HTTPConnection, str], typing.Awaitable[UserLike | None]]


class SessionAuthenticator:
    def __init__(
        self,
        user_loader: ByIdUserFinder,
        *,
        session_key: str = SESSION_KEY,
    ) -> None:
        self.user_loader = user_loader
        self.session_key = session_key

    async def __call__(self, connection: HTTPConnection) -> AuthToken | None:
        if user_id := connection.session.get(SESSION_KEY):
            if user := await self.user_loader(connection, user_id):
                return AuthToken(user=user, state=LoginState.FRESH)
        return None


class RememberMeAuthenticator:
    def __init__(
        self,
        user_loader: ByIdUserFinder,
        secret_key: str,
        *,
        cookie_name: str = REMEMBER_COOKIE_NAME,
    ) -> None:
        self.secret_key = secret_key
        self.user_loader = user_loader
        self.cookie_name = cookie_name

    async def __call__(self, connection: HTTPConnection) -> AuthToken | None:
        if cookie_value := connection.cookies.get(self.cookie_name):
            try:
                signer = Signer(secret_key=self.secret_key)
                user_id = signer.unsign(cookie_value).decode("utf8")
                if user := await self.user_loader(connection, user_id):
                    return AuthToken(user=user, state=LoginState.REMEMBERED)
            except BadSignature:
                return None
        return None


class AuthenticationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        authenticators: typing.Iterable[Authenticator],
        on_success: typing.Callable[[HTTPConnection, AuthToken], typing.Awaitable[None]] | None = None,
    ) -> None:
        self.app = app
        self.on_success = on_success
        self.authenticators = authenticators

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        auth_token = AuthToken(user=AnonymousUser(), state=LoginState.ANONYMOUS)
        connection = HTTPConnection(scope, receive)

        for authenticator in self.authenticators:
            if token := await authenticator(connection):
                assert isinstance(token, AuthToken), "Authenticator must return AuthToken instance or None."
                auth_token = token
                if self.on_success:
                    await self.on_success(connection, auth_token)
                break

        scope["auth"] = auth_token
        await self.app(scope, receive, send)


async def login(connection: HTTPConnection, user: UserLike) -> AuthToken:
    """Login user."""

    # Regenerate session id to prevent session fixation.
    # Attack vector:
    # A malicious user can steal session ID from victim's browser and set it into his own
    # When victim sign in and session NOT regenerated then two browsers will share same session and data
    # Force session regeneration.
    _regenerate_session_id(connection)

    auth_token = AuthToken(user=user, state=LoginState.FRESH)
    connection.scope["auth"] = auth_token
    connection.session[SESSION_KEY] = user.get_id()

    return auth_token


async def logout(connection: HTTPConnection) -> None:
    connection.session.clear()  # wipe all data
    _regenerate_session_id(connection)
    connection.scope["auth"] = AuthToken(user=AnonymousUser(), state=LoginState.ANONYMOUS)


def is_authenticated(connection: HTTPConnection) -> bool:
    return connection.auth.is_authenticated


def confirm_login(connection: HTTPConnection) -> None:
    if connection.scope["auth"].is_authenticated:  #
        connection.scope["auth"].change_state(LoginState.FRESH)


def remember_me(
    response: Response,
    secret_key: str,
    user: UserLike,
    duration: datetime.timedelta,
    *,
    cookie_name: str = REMEMBER_COOKIE_NAME,
    cookie_path: str = "/",
    cookie_domain: str | None = None,
    cookie_samesite: typing.Literal["lax", "strict", "none"] = "lax",
    cookie_secure: bool = False,
    cookie_http_only: bool = True,
) -> Response:
    signer = Signer(secret_key)
    value = signer.sign(user.get_id()).decode("utf8")

    response.set_cookie(
        key=cookie_name,
        value=value,
        max_age=int(duration.total_seconds()),
        path=cookie_path,
        domain=cookie_domain,
        secure=cookie_secure,
        httponly=cookie_http_only,
        samesite=cookie_samesite,
    )
    return response


def forget_me(
    response: Response,
    *,
    cookie_name: str = REMEMBER_COOKIE_NAME,
    cookie_path: str = "/",
    cookie_domain: str | None = None,
    cookie_samesite: typing.Literal["lax", "strict", "none"] = "lax",
    cookie_secure: bool = False,
    cookie_http_only: bool = True,
) -> Response:
    response.set_cookie(
        key=cookie_name,
        value="null",
        max_age=-1,
        path=cookie_path,
        domain=cookie_domain,
        secure=cookie_secure,
        httponly=cookie_http_only,
        samesite=cookie_samesite,
    )
    return response


def _regenerate_session_id(connection: HTTPConnection) -> None:
    if "session_handler" in connection.scope:  # when starsessions installed
        from starsessions import regenerate_session_id

        regenerate_session_id(connection)
