import typing as t
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.contracts import Authenticator, Identity, IdentityProvider, PasswordHasher
from kupala.requests import Request

SESSION_KEY = "_user"


class AuthenticationError(Exception):
    ...


class LoginFailedError(AuthenticationError):
    ...


@dataclass
class AuthState:
    user: t.Optional[Identity] = None

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None

    def clear(self) -> None:
        self.user = None

    def __bool__(self) -> bool:
        return self.is_authenticated

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Identity):
            return NotImplemented

        if self.user is None:
            return False

        return other.get_id() == self.user.get_id()


class LoginManager:
    def __init__(
        self,
        user_provider: IdentityProvider,
        hasher: PasswordHasher = None,
    ) -> None:
        self.user_provider = user_provider
        self.hasher = hasher

    async def login(self, request: Request, identity: str, credential: str) -> Identity:
        user = await self.user_provider.find_by_identity(identity)
        if user:
            hasher = self.hasher or request.app.get(PasswordHasher)
            hashed = user.get_hashed_password()
            if hasher.verify(credential, hashed):
                request.session[SESSION_KEY] = user.get_id()
                return user
        raise LoginFailedError("Credentials are invalid.")

    async def logout(self, request: Request) -> None:
        request.session.clear()
        await request.session.regenerate_id()
        request.auth.clear()


class SessionAuthenticator:
    def __init__(self, user_provider: IdentityProvider):
        self.user_provider = user_provider

    async def authenticate(self, request: Request) -> t.Optional[Identity]:
        if "session" not in request.scope:
            raise KeyError("AuthenticationMiddleware requires SessionMiddleware.")
        user_id = request.session.get(SESSION_KEY)
        if not user_id:
            return None
        return await self.user_provider.find_by_id(user_id)


class TokenAuthenticator:
    def __init__(self, user_provider: IdentityProvider, token: str = "Bearer"):
        self.user_provider = user_provider
        self.token = token

    async def authenticate(self, request: Request) -> t.Optional[Identity]:
        header = request.headers.get("Authorization")
        if header:
            token_type, value = header.split(" ")
            if token_type == self.token:
                return await self.user_provider.find_by_token(value)
        return None


class AuthenticationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        authenticators: list[t.Union[Authenticator, str]] = None,
    ) -> None:
        self.app = app
        self.authenticators = authenticators or []

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        scope["auth"] = AuthState()
        request: Request = scope["request"]
        for authenticator in self.authenticators:
            if isinstance(authenticator, str):
                authenticator = f"authenticator.{authenticator}"
            authenticator = t.cast(Authenticator, request.app.get(authenticator))
            user = await authenticator.authenticate(request)
            if user:
                scope["auth"] = AuthState(user)
                break
        await self.app(scope, receive, send)


class InMemoryProvider(IdentityProvider):
    def __init__(self, users: list[Identity]):
        self.users = users

    @property
    def by_id(self) -> dict[str, Identity]:
        return {u.get_id(): u for u in self.users}

    @property
    def by_identity(self) -> dict[str, Identity]:
        return {u.get_identity(): u for u in self.users}

    async def find_by_identity(self, identity: str) -> t.Optional[Identity]:
        return self.by_identity.get(identity)

    async def find_by_id(self, id: t.Any) -> t.Optional[Identity]:
        return self.by_id.get(id)

    async def find_by_token(self, token: str) -> t.Optional[Identity]:
        return self.by_identity.get(token)
