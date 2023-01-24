import pytest
from itsdangerous import URLSafeTimedSerializer
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse

from kupala.exceptions import PermissionDenied
from kupala.middleware import Middleware
from kupala.middleware.csrf import (
    CSRFError,
    CSRFMiddleware,
    TokenDecodeError,
    TokenExpiredError,
    TokenMismatchError,
    TokenMissingError,
    generate_token,
    get_csrf_input,
    get_csrf_meta_tag,
    get_csrf_token,
    validate_csrf_token,
)
from kupala.requests import Request
from kupala.routing import route
from tests.conftest import ClientFactory


@pytest.fixture()
def csrf_token() -> str:
    secret_key = "secret"
    return generate_token(secret_key, "123456")


@pytest.fixture()
def csrf_timed_token(csrf_token: str) -> str:
    secret_key = "secret"
    salt = "_salt_"
    return str(URLSafeTimedSerializer(secret_key, salt).dumps(csrf_token))


def test_csrf_token(csrf_token: str, csrf_timed_token: str) -> None:
    assert validate_csrf_token(csrf_token, csrf_timed_token, "secret", "_salt_")


def test_validate_csrf_token_needs_token(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenMissingError) as ex:
        assert validate_csrf_token("", csrf_timed_token, "secret", "_salt_")
    assert str(ex.value) == "CSRF token is missing."

    with pytest.raises(TokenMissingError) as ex:
        assert validate_csrf_token(csrf_token, "", "secret", "_salt_")
    assert str(ex.value) == "CSRF token is missing."


def test_validate_csrf_token_expired_token(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenExpiredError) as ex:
        validate_csrf_token(csrf_token, csrf_timed_token, "secret", "_salt_", max_age=-1)
    assert str(ex.value) == "CSRF token has expired."


def test_validate_csrf_token_bad_data(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenDecodeError) as ex:
        validate_csrf_token(csrf_token, csrf_timed_token, "secret1", "_salt_")
    assert str(ex.value) == "CSRF token is invalid."


def test_validate_csrf_token_mismatch(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenMismatchError) as ex:
        validate_csrf_token("invalid", csrf_timed_token, "secret", "_salt_")
    assert str(ex.value) == "CSRF tokens do not match."


def test_middleware_needs_session(test_client_factory: ClientFactory) -> None:
    client = test_client_factory(
        middleware=[
            Middleware(CSRFMiddleware, secret_key="secret"),
        ]
    )
    with pytest.raises(CSRFError) as ex:
        client.get("/")
    assert str(ex.value) == "CsrfMiddleware requires SessionMiddleware."


def test_middleware_checks_access(test_client_factory: ClientFactory) -> None:
    @route("/", methods=["post", "get", "head", "put", "delete", "patch", "options"])
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(CSRFMiddleware, secret_key="key!"),
        ],
    )

    assert client.get("/").status_code == 200
    assert client.head("/").status_code == 200
    response = client.options("/")
    assert response.status_code == 200

    # test POST, PUT, DELETE, PATCH are denied without token
    with pytest.raises(PermissionDenied):
        assert client.post("/")

    with pytest.raises(PermissionDenied):
        assert client.put("/").status_code

    with pytest.raises(PermissionDenied):
        assert client.patch("/").status_code

    with pytest.raises(PermissionDenied):
        assert client.delete("/").status_code

    # test POST, PUT, DELETE, PATCH are allowed with token
    token = response.text
    assert client.post("/", data={"_token": token}).status_code == 200
    assert client.post(f"/?csrf-token={token}").status_code == 200
    assert client.post("/", headers={"x-csrf-token": token}).status_code == 200

    assert client.put("/", data={"_token": token}).status_code == 200
    assert client.put(f"/?csrf-token={token}").status_code == 200
    assert client.put("/", headers={"x-csrf-token": token}).status_code == 200

    assert client.patch("/", data={"_token": token}).status_code == 200
    assert client.patch(f"/?csrf-token={token}").status_code == 200
    assert client.patch("/", headers={"x-csrf-token": token}).status_code == 200

    assert client.delete(f"/?csrf-token={token}").status_code == 200
    assert client.delete("/", headers={"x-csrf-token": token}).status_code == 200


def test_middleware_allow_from_whitelist(test_client_factory: ClientFactory) -> None:
    @route("/", methods=["post", "options"])
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    @route("/login", methods=["post"])
    def login_view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    client = test_client_factory(
        routes=[view, login_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(CSRFMiddleware, secret_key="secret", exclude_urls=[r"/login"]),
        ],
    )

    response = client.options("/")
    assert response.status_code == 200
    token = response.text

    assert client.post("/", data={"_token": token}).status_code == 200
    assert client.post("/login").status_code == 200


def test_middleware_allow_from_whitelist_using_full_url(test_client_factory: ClientFactory) -> None:
    @route("/", methods=["post"])
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(CSRFMiddleware, secret_key="secret", exclude_urls=["http://testserver/"]),
        ],
    )

    assert client.post("/").status_code == 200


def test_middleware_injects_template_context(test_client_factory: ClientFactory) -> None:
    @route("/", methods=["post"])
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(CSRFMiddleware, secret_key="secret", exclude_urls=["http://testserver/"]),
        ],
    )
    assert client.post("/").status_code == 200


def test_get_csrf_token_helper(test_client_factory: ClientFactory) -> None:
    request = Request({"type": "http", "state": {"csrf_timed_token": "token"}})
    assert get_csrf_token(request) == "token"

    request = Request({"type": "http", "state": {}})
    assert get_csrf_token(request) is None


def test_get_csrf_input_helper(test_client_factory: ClientFactory) -> None:
    request = Request({"type": "http", "state": {"csrf_timed_token": "token"}})
    assert get_csrf_input(request) == '<input type="hidden" name="_token" value="token">'


def test_get_csrf_meta_tag_helper(test_client_factory: ClientFactory) -> None:
    request = Request({"type": "http", "state": {"csrf_timed_token": "token"}})
    assert get_csrf_meta_tag(request) == '<meta name="csrf-token" content="token">'
