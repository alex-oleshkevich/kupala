import pytest
from itsdangerous import URLSafeTimedSerializer
from starlette.testclient import TestClient
from starsessions import SessionMiddleware

from kupala.application import Kupala
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
    validate_csrf_token,
)
from kupala.middleware.template_context import TemplateContextMiddleware
from kupala.requests import Request
from kupala.responses import PlainTextResponse


@pytest.fixture()
def csrf_token() -> str:
    secret_key = 'secret'
    return generate_token(secret_key, '123456')


@pytest.fixture()
def csrf_timed_token(csrf_token: str) -> str:
    secret_key = 'secret'
    salt = '_salt_'
    return str(URLSafeTimedSerializer(secret_key, salt).dumps(csrf_token))


def test_csrf_token(csrf_token: str, csrf_timed_token: str) -> None:
    assert validate_csrf_token(csrf_token, csrf_timed_token, 'secret', '_salt_')


def test_validate_csrf_token_needs_token(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenMissingError) as ex:
        assert validate_csrf_token('', csrf_timed_token, 'secret', '_salt_')
    assert str(ex.value) == 'CSRF token is missing.'

    with pytest.raises(TokenMissingError) as ex:
        assert validate_csrf_token(csrf_token, '', 'secret', '_salt_')
    assert str(ex.value) == 'CSRF token is missing.'


def test_validate_csrf_token_expired_token(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenExpiredError) as ex:
        validate_csrf_token(csrf_token, csrf_timed_token, 'secret', '_salt_', max_age=-1)
    assert str(ex.value) == 'CSRF token has expired.'


def test_validate_csrf_token_bad_data(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenDecodeError) as ex:
        validate_csrf_token(csrf_token, csrf_timed_token, 'secret1', '_salt_')
    assert str(ex.value) == 'CSRF token is invalid.'


def test_validate_csrf_token_mismatch(csrf_token: str, csrf_timed_token: str) -> None:
    with pytest.raises(TokenMismatchError) as ex:
        validate_csrf_token('invalid', csrf_timed_token, 'secret', '_salt_')
    assert str(ex.value) == 'CSRF tokens do not match.'


def test_middleware_needs_session() -> None:
    app = Kupala()
    app.middleware.use(CSRFMiddleware, secret_key='secret')
    with pytest.raises(CSRFError) as ex:
        client = TestClient(app)
        client.get('/')
    assert str(ex.value) == 'CsrfMiddleware requires SessionMiddleware.'


def test_middleware_checks_access() -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    app = Kupala()
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(CSRFMiddleware, secret_key='key!')
    app.routes.add('/', view, methods=['post', 'get', 'head', 'put', 'delete', 'patch', 'options'])

    client = TestClient(app)
    assert client.get('/').status_code == 200
    assert client.head('/').status_code == 200
    response = client.options('/')
    assert response.status_code == 200

    # test POST, PUT, DELETE, PATCH are denied without token
    with pytest.raises(PermissionDenied):
        assert client.post('/')

    with pytest.raises(PermissionDenied):
        assert client.put('/').status_code

    with pytest.raises(PermissionDenied):
        assert client.patch('/').status_code

    with pytest.raises(PermissionDenied):
        assert client.delete('/').status_code

    # test POST, PUT, DELETE, PATCH are allowed with token
    token = response.text
    assert client.post('/', {'_token': token}).status_code == 200
    assert client.post(f'/?csrf-token={token}').status_code == 200
    assert client.post('/', headers={'x-csrf-token': token}).status_code == 200

    assert client.put('/', {'_token': token}).status_code == 200
    assert client.put(f'/?csrf-token={token}').status_code == 200
    assert client.put('/', headers={'x-csrf-token': token}).status_code == 200

    assert client.patch('/', {'_token': token}).status_code == 200
    assert client.patch(f'/?csrf-token={token}').status_code == 200
    assert client.patch('/', headers={'x-csrf-token': token}).status_code == 200

    assert client.delete(f'/?csrf-token={token}').status_code == 200
    assert client.delete('/', headers={'x-csrf-token': token}).status_code == 200


def test_middleware_allow_from_whitelist() -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    app = Kupala(
        middleware=[
            Middleware(SessionMiddleware, secret_key='secret'),
            Middleware(CSRFMiddleware, secret_key='secret', exclude_urls=[r'/login']),
        ]
    )

    app.routes.add('/', view, methods=['post', 'options'])
    app.routes.add('/login', view, methods=['post'])

    client = TestClient(app)
    response = client.options('/')
    assert response.status_code == 200
    token = response.text

    assert client.post('/', {'_token': token}).status_code == 200
    assert client.post('/login').status_code == 200


def test_middleware_allow_from_whitelist_using_full_url() -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    app = Kupala(
        middleware=[
            Middleware(SessionMiddleware, secret_key='secret', autoload=True),
            Middleware(CSRFMiddleware, secret_key='secret', exclude_urls=['http://testserver/']),
        ]
    )
    app.routes.add('/', view, methods=['post'])

    client = TestClient(app)
    assert client.post('/').status_code == 200


def test_middleware_injects_template_context() -> None:
    def view(request: Request) -> PlainTextResponse:
        return PlainTextResponse(request.state.csrf_timed_token)

    app = Kupala(
        middleware=[
            Middleware(TemplateContextMiddleware),
            Middleware(SessionMiddleware, secret_key='secret', autoload=True),
            Middleware(CSRFMiddleware, secret_key='secret', exclude_urls=['http://testserver/']),
        ]
    )
    app.routes.add('/', view, methods=['post'])

    client = TestClient(app)
    assert client.post('/').status_code == 200
