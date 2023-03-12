import datetime
import itsdangerous
import typing
from starlette.authentication import AuthCredentials, AuthenticationBackend, BaseUser, UnauthenticatedUser
from starlette.datastructures import URL
from starlette.requests import HTTPConnection, Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.guards import Guard, NextGuard

SESSION_KEY = "__user_id__"
REMEMBER_COOKIE_NAME = "remember_me"

ByIdUserFinder = typing.Callable[[HTTPConnection, str], typing.Awaitable[BaseUser | None]]


@typing.runtime_checkable
class UserWithScopes(typing.Protocol):  # pragma: no cover
    def get_scopes(self) -> list[str]:
        ...


def get_scopes(user: BaseUser | UserWithScopes) -> list[str]:
    if isinstance(user, UserWithScopes):
        return user.get_scopes()
    return []


class LoginScopes:
    FRESH = "login:fresh"
    REMEMBERED = "login:remembered"


class SessionBackend(AuthenticationBackend):
    def __init__(self, user_loader: ByIdUserFinder) -> None:
        self.user_loader = user_loader

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        user_id: str = conn.session.get(SESSION_KEY, "")
        if user_id and (user := await self.user_loader(conn, user_id)):
            return AuthCredentials(scopes=get_scopes(user)), user
        return None


class RememberMeBackend(AuthenticationBackend):
    """
    Authenticates user using "remember me" cookie.

    It also adds "login:remembered" scope to distinguish between fresh and remembered logins.
    """

    def __init__(
        self,
        user_loader: ByIdUserFinder,
        secret_key: str,
        duration: datetime.timedelta | None = None,
        *,
        cookie_name: str = REMEMBER_COOKIE_NAME,
    ) -> None:
        self.secret_key = secret_key
        self.user_loader = user_loader
        self.cookie_name = cookie_name
        self.duration = duration

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        if cookie_value := conn.cookies.get(self.cookie_name):
            try:
                max_age = int(self.duration.total_seconds()) if self.duration else None
                signer = itsdangerous.TimestampSigner(secret_key=self.secret_key)
                user_id = signer.unsign(cookie_value, max_age=max_age).decode("utf8")
                if user := await self.user_loader(conn, user_id):
                    return AuthCredentials(scopes=get_scopes(user) + [LoginScopes.REMEMBERED]), user
            except itsdangerous.BadSignature:
                return None
        return None


class ChoiceBackend(AuthenticationBackend):
    def __init__(self, backends: list[AuthenticationBackend]) -> None:
        self.backends = backends

    async def authenticate(self, conn: HTTPConnection) -> typing.Optional[typing.Tuple[AuthCredentials, BaseUser]]:
        for backend in self.backends:
            if result := await backend.authenticate(conn):
                return result
        return None


def _regenerate_session_id(connection: HTTPConnection) -> None:
    if "session_handler" in connection.scope:  # when starsessions installed
        from starsessions import regenerate_session_id

        regenerate_session_id(connection)


async def login(connection: HTTPConnection, user: BaseUser) -> None:
    """Login user."""

    # Regenerate session id to prevent session fixation.
    # Attack vector:
    # A malicious user can steal session ID from victim's browser and set it into his own
    # When victim sign in and session NOT regenerated then two browsers will share same session and data
    # Force session regeneration.
    _regenerate_session_id(connection)

    connection.scope["auth"] = AuthCredentials(scopes=get_scopes(user) + [LoginScopes.FRESH])
    connection.scope["user"] = user
    connection.session[SESSION_KEY] = user.identity


async def logout(connection: HTTPConnection) -> None:
    connection.session.clear()  # wipe all data
    _regenerate_session_id(connection)
    connection.scope["auth"] = AuthCredentials()
    connection.scope["user"] = UnauthenticatedUser()


def is_authenticated(connection: HTTPConnection) -> bool:
    return connection.auth and connection.user.is_authenticated


def confirm_login(connection: HTTPConnection) -> None:
    credentials: AuthCredentials = connection.auth
    if LoginScopes.REMEMBERED in credentials.scopes:
        credentials.scopes.append(LoginScopes.FRESH)
        connection.session[SESSION_KEY] = connection.user.identity
        if LoginScopes.REMEMBERED in credentials.scopes:
            credentials.scopes.remove(LoginScopes.REMEMBERED)


def remember_me(
    response: Response,
    secret_key: str,
    user: BaseUser,
    duration: datetime.timedelta,
    *,
    cookie_name: str = REMEMBER_COOKIE_NAME,
    cookie_path: str = "/",
    cookie_domain: str | None = None,
    cookie_samesite: typing.Literal["lax", "strict", "none"] = "lax",
    cookie_secure: bool = False,
    cookie_http_only: bool = True,
) -> Response:
    signer = itsdangerous.TimestampSigner(secret_key)
    value = signer.sign(user.identity).decode("utf8")
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


def login_required(
    redirect_url: str | None = None,
    *,
    path_name: str | None = "login",
    path_params: dict[str, typing.Any] | None = None,
) -> Guard:
    assert redirect_url or path_name
    path_params = path_params or {}

    async def guard(request: Request, call_next: NextGuard) -> Response:
        if not request.user.is_authenticated:
            redirect_to = redirect_url or request.url_for(path_name, **path_params)  # type: ignore[arg-type]
            url = URL(str(redirect_to)).include_query_params(next=request.url.path)
            return RedirectResponse(url, 302)

        return await call_next(request)

    return guard


class LoginRequiredMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        redirect_url: str | None = None,
        *,
        path_name: str | None = "login",
        path_params: dict[str, typing.Any] | None = None,
    ) -> None:
        assert redirect_url or path_name
        self.app = app
        self.redirect_url = redirect_url
        self.path_name = path_name
        self.path_params = path_params or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        user = typing.cast(BaseUser, scope.get("user"))
        if not user.is_authenticated:
            request = Request(scope, receive, send)
            redirect_to = self.redirect_url or request.app.url_path_for(
                self.path_name, **self.path_params
            )  # type: ignore[arg-type]
            url = URL(redirect_to).include_query_params(next=request.url.path)
            response = RedirectResponse(url, 302)
            await response(scope, receive, send)
        else:
            await self.app(scope, receive, send)
