from starsessions import SessionMiddleware

from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import JSONResponse, RedirectResponse
from kupala.routing import Route
from kupala.testclient import TestClient


async def set_view(request: Request) -> RedirectResponse:
    await request.remember_form_data()
    return RedirectResponse('/get')


def get_view(request: Request) -> JSONResponse:
    return JSONResponse(request.old_input)


def test_old_input() -> None:
    app = Kupala(routes=[Route('/', set_view, methods=['POST']), Route('/get', get_view)])
    app.middleware.use(SessionMiddleware, secret_key='key', autoload=True)
    client = TestClient(app)

    with open('/tmp/test1.txt', 'wb') as f:
        f.write(b'content')

    with open('/tmp/test1.txt', 'rb') as f:
        response = client.post(
            '/',
            allow_redirects=True,
            data=[('first_name', 'root'), ('last_name', 'user')],
            files=[('avatar', f)],
        )
        assert response.status_code == 200
        assert response.json() == {
            'first_name': 'root',
            'last_name': 'user',
        }

    # when accessing page for the second time, the session data has to be absent
    response = client.get('/get')
    assert response.json() == {}


def test_old_input_without_session() -> None:
    app = Kupala(routes=[Route('/', set_view, methods=['POST']), Route('/get', get_view)])
    client = TestClient(app)

    response = client.post(
        '/',
        allow_redirects=True,
        data=[('first_name', 'root'), ('last_name', 'user')],
    )
    assert response.status_code == 200
    assert response.json() == {}

    # when accessing page for the second time, the session data has to be absent
    assert response.json() == {}


async def set_form_errors_view(request: Request) -> RedirectResponse:
    request.set_form_errors(
        'Form is invalid.',
        {
            'first_name': ['This field is required.'],
            'last_name': ['This field is required.'],
        },
    )
    return RedirectResponse('/get')


def get_form_errors_view(request: Request) -> JSONResponse:
    return JSONResponse(request.form_errors)


def test_form_errors() -> None:
    app = Kupala(routes=[Route('/', set_form_errors_view, methods=['POST']), Route('/get', get_form_errors_view)])
    app.middleware.use(SessionMiddleware, secret_key='key', autoload=True)
    client = TestClient(app)

    response = client.post(
        '/',
        allow_redirects=True,
        data={
            'first_name': 'root',
            'last_name': 'user',
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        'message': 'Form is invalid.',
        'field_errors': {
            'first_name': ['This field is required.'],
            'last_name': ['This field is required.'],
        },
    }

    # when accessing page for the second time, the session data has to be absent
    response = client.get('/get')
    assert response.json() == {'message': '', 'field_errors': {}}


def test_form_errors_without_session() -> None:
    app = Kupala(routes=[Route('/', set_form_errors_view, methods=['POST']), Route('/get', get_form_errors_view)])
    client = TestClient(app)

    response = client.post(
        '/',
        allow_redirects=True,
        data={
            'first_name': 'root',
            'last_name': 'user',
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        'message': '',
        'field_errors': {},
    }

    # when accessing page for the second time, the session data has to be absent
    response = client.get('/get')
    assert response.json() == {'message': '', 'field_errors': {}}
