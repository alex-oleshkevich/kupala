import dataclasses

import pytest
from starlette.testclient import TestClient

from kupala.authentication import (
    SESSION_KEY,
    AuthenticationMiddleware,
    AuthState,
    InMemoryProvider,
    LoginManager,
    SessionAuthenticator,
    TokenAuthenticator,
)
from kupala.responses import TextResponse
from kupala.security.hashers import InsecureHasher
from kupala.sessions import InMemoryBackend, SessionMiddleware


@dataclasses.dataclass
class User:
    email: str
    password: str

    def get_identity(self) -> str:
        return self.email

    def get_id(self) -> str:
        return self.email

    def get_hashed_password(self) -> str:
        return self.password


@pytest.fixture()
def user_provider():
    return InMemoryProvider(
        [
            User("user@example.com", "password"),
        ]
    )


@pytest.mark.asyncio
async def test_in_memory_provider():
    provider = InMemoryProvider(
        [
            User("user@example.com", "password"),
        ]
    )

    assert await provider.find_by_identity("user@example.com")
    assert not await provider.find_by_identity("missing@example.com")

    assert await provider.find_by_id("user@example.com")
    assert not await provider.find_by_id("missing@example.com")

    assert await provider.find_by_token("user@example.com")
    assert not await provider.find_by_token("missing@example.com")


def test_auth_state():
    state = AuthState()
    assert not state.is_authenticated
    assert state.is_anonymous
    assert state.user is None

    state = AuthState(user=User("user@localhost", "hashed_password"))
    assert state.is_authenticated
    assert not state.is_anonymous
    assert state.user is not None

    if state:
        assert True
    else:
        assert False  # should never happen

    state.clear()
    assert state.is_anonymous


def test_login_manager(app_f, user_provider):
    """Login manager should successfully login user
    with a valid credentials."""
    user = None
    request_after_login = None
    request_after_logout = old_session_id = new_session_id = None

    async def login_view(request):
        nonlocal user, request_after_login
        request_after_login = request
        manager = request.app.get(LoginManager)
        user = await manager.login(request, "user@example.com", "password")
        return TextResponse("ok")

    async def logout_view(request):
        nonlocal request_after_logout, old_session_id, new_session_id
        request_after_logout = request
        old_session_id = request.session.session_id

        manager = request.app.get(LoginManager)
        await manager.logout(request)

        new_session_id = request.session.session_id
        return TextResponse("ok")

    app = app_f()
    app.middleware.use(SessionMiddleware, secret_key="secret")
    app.bind(LoginManager, LoginManager(user_provider, InsecureHasher()))
    app.bind("authenticator.session", SessionAuthenticator(user_provider))

    with app.middleware.group("auth") as auth:
        auth.use(AuthenticationMiddleware, authenticators=["session"])

    app.routes.get("/login", login_view)
    with app.routes.group("/app", ["auth"]) as app_routes:
        app_routes.post("/logout", logout_view)

    client = TestClient(app)

    # login
    response = client.get("/login")
    assert response.status_code == 200
    assert user is not None
    assert user.email == "user@example.com"
    assert SESSION_KEY in request_after_login.session

    # # logout
    response = client.post("/app/logout")
    assert response.status_code == 200
    assert SESSION_KEY not in request_after_logout.session
    assert old_session_id != new_session_id


def test_login_manager_fail(app_f, user_provider):
    """Login manager must return None if it cannot authenticate user."""
    app = app_f()
    app.middleware.use(SessionMiddleware, secret_key="secret")
    app.bind(LoginManager, LoginManager(user_provider, InsecureHasher()))

    user = None
    used_request = None

    async def view(request):
        nonlocal user, used_request
        used_request = request
        manager = request.app.get(LoginManager)
        user = await manager.login(request, "user@example.com", "invalid")
        return TextResponse("ok")

    app.routes.get("/", view)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert user is None
    assert SESSION_KEY not in used_request.session


def test_authentication_middleware_session(app_f, test_client, user_provider):
    """AuthenticationMiddleware should authenticate user using session.
    SessionAuthenticator must load user from the session using SESSION_KEY
    and pass it to the request via AuthState class.
    """
    session_id = "SID"
    backend = InMemoryBackend({session_id: {"_user": "user@example.com"}})
    app = app_f()
    app.bind("authenticator.session", SessionAuthenticator(user_provider))
    app.middleware.use(SessionMiddleware, secret_key="secret", backend=backend)
    app.middleware.use(AuthenticationMiddleware, authenticators=["session"])

    auth: AuthState = None

    def view(request):
        nonlocal auth
        auth = request.auth
        return TextResponse("ok")

    app.routes.get("/", view)

    client = TestClient(app)
    response = client.get(
        "/",
        allow_redirects=False,
        cookies={
            "session": session_id,
        },
    )
    assert response.status_code == 200
    assert auth is not None
    assert auth.is_authenticated
    assert auth.user.get_id() == "user@example.com"


def test_authentication_middleware_session_user_not_found(
    app_f, test_client, user_provider
):
    """AuthenticationMiddleware should NOT authenticate user
    if user cannot be loaded by the provider.."""
    session_id = "SID"
    backend = InMemoryBackend({session_id: {"_user": "missing@example.com"}})
    app = app_f()
    app.bind("authenticator.session", SessionAuthenticator(user_provider))
    app.middleware.use(SessionMiddleware, secret_key="secret", backend=backend)
    app.middleware.use(AuthenticationMiddleware, authenticators=["session"])

    auth: AuthState = None

    def view(request):
        nonlocal auth
        auth = request.auth
        return TextResponse("ok")

    app.routes.get("/", view)

    client = TestClient(app)
    response = client.get(
        "/",
        allow_redirects=False,
        cookies={
            "session": session_id,
        },
    )
    assert response.status_code == 200
    assert auth is not None
    assert not auth.is_authenticated


def test_authentication_middleware_token(app_f, test_client, user_provider):
    """AuthenticationMiddleware should authenticate user using session.
    TokenAuthenticator must load user using user token from the request
    and pass it to the request via AuthState class.
    """
    app = app_f()
    app.bind("authenticator.token", TokenAuthenticator(user_provider))
    app.middleware.use(AuthenticationMiddleware, authenticators=["token"])

    auth: AuthState = None

    def view(request):
        nonlocal auth
        auth = request.auth
        return TextResponse("ok")

    app.routes.get("/", view)

    client = TestClient(app)
    response = client.get(
        "/",
        allow_redirects=False,
        headers={
            "Authorization": "Bearer user@example.com",
        },
    )
    assert response.status_code == 200
    assert auth is not None
    assert auth.is_authenticated
    assert auth.user.get_id() == "user@example.com"


def test_authentication_middleware_invalid_token_value(
    app_f,
    test_client,
    user_provider,
):
    """AuthenticationMiddleware should NOT authenticate user
    if the provided token is invalid."""
    app = app_f()
    app.bind("authenticator.token", TokenAuthenticator(user_provider))
    app.middleware.use(AuthenticationMiddleware, authenticators=["token"])

    auth: AuthState = None

    def view(request):
        nonlocal auth
        auth = request.auth
        return TextResponse("ok")

    app.routes.get("/", view)

    client = TestClient(app)
    response = client.get(
        "/",
        allow_redirects=False,
        headers={
            "Authorization": "Bearer invalid@example.com",
        },
    )
    assert response.status_code == 200
    assert auth is not None
    assert not auth.is_authenticated


def test_authentication_middleware_unsupported_token_type(
    app_f,
    test_client,
    user_provider,
):
    """AuthenticationMiddleware should NOT authenticate user
    if the token type is not supported."""
    app = app_f()
    app.bind("authenticator.token", TokenAuthenticator(user_provider))
    app.middleware.use(AuthenticationMiddleware, authenticators=["token"])

    auth: AuthState = None

    def view(request):
        nonlocal auth
        auth = request.auth
        return TextResponse("ok")

    app.routes.get("/", view)

    client = TestClient(app)
    response = client.get(
        "/",
        allow_redirects=False,
        headers={
            "Authorization": "JWT invalid@example.com",
        },
    )
    assert response.status_code == 200
    assert auth is not None
    assert not auth.is_authenticated
