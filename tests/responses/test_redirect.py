import pytest
from starsessions import SessionMiddleware

from kupala.application import Kupala
from kupala.http.middleware import Middleware
from kupala.http.middleware.flash_messages import FlashMessagesMiddleware, flash
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse, RedirectResponse
from kupala.testclient import TestClient

REDIRECT_INPUT_DATA_SESSION_KEY = "_form_old_input"


def test_redirect() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about')

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/', allow_redirects=False)
    assert response.headers['location'] == '/about'


def test_redirect_requires_url_or_path_name() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse()

    app = Kupala()
    app.routes.add('/', view)

    with pytest.raises(AssertionError) as ex:
        client = TestClient(app)
        client.get('/')
    assert str(ex.value) == 'Either "url" or "path_name" argument must be passed.'


def test_redirect_to_path_name() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse(path_name='about')

    app = Kupala()
    app.routes.add('/', view)
    app.routes.add('/about', view, name='about')

    client = TestClient(app)
    response = client.get('/', allow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == '/about'


def test_redirect_to_path_name_with_path_params() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse(path_name='about', path_params={'id': 42})

    app = Kupala()
    app.routes.add('/', view)
    app.routes.add('/about/{id}', view, name='about')

    client = TestClient(app)
    response = client.get('/', allow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == '/about/42'


def test_redirect_with_input_capture() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about', capture_input=True)

    def data_view(request: Request) -> JSONResponse:
        return JSONResponse(request.old_input)

    app = Kupala()
    app.routes.add('/', view, methods=['post'])
    app.routes.add('/about', data_view, name='about')

    app = SessionMiddleware(app, secret_key='key!', autoload=True)
    client = TestClient(app)
    response = client.post('/', allow_redirects=True, data={'id': '42', 'name': 'test'})
    assert response.status_code == 200
    assert response.json() == {'id': '42', 'name': 'test'}


def test_redirect_with_input_data_via_method() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about').with_input()

    def data_view(request: Request) -> JSONResponse:
        return JSONResponse(request.session[REDIRECT_INPUT_DATA_SESSION_KEY])

    app = Kupala()
    app.routes.add('/', view, methods=['post'])
    app.routes.add('/about', data_view, name='about')

    app = SessionMiddleware(app, secret_key='key!', autoload=True)
    client = TestClient(app)
    response = client.post('/', allow_redirects=True, data={'id': 42, 'name': 'test'})
    assert response.status_code == 200
    assert response.json() == {'id': '42', 'name': 'test'}


def test_redirect_with_flash_message() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about', flash_message='Saved.', flash_category='success')

    def data_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    app = Kupala()
    app.routes.add('/', view)
    app.routes.add('/about', data_view, name='about')
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(FlashMessagesMiddleware, storage='session')

    client = TestClient(app)
    response = client.get('/', allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{'category': 'success', 'message': 'Saved.'}]


def test_redirect_with_flash_message_via_method() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about').flash('Saved.')

    def data_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    app = Kupala()
    app.routes.add('/', view)
    app.routes.add('/about', data_view, name='about')
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(FlashMessagesMiddleware, storage='session')

    client = TestClient(app)
    response = client.get('/', allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{'category': 'success', 'message': 'Saved.'}]


def test_redirect_with_success() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about').with_success('Saved.')

    def data_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    app = Kupala()
    app.routes.add('/', view)
    app.routes.add('/about', data_view, name='about')
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(FlashMessagesMiddleware, storage='session')

    client = TestClient(app)
    response = client.get('/', allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{'category': 'success', 'message': 'Saved.'}]


def test_redirect_with_error() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about').with_error('Error.')

    def data_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(messages)

    app = Kupala()
    app.routes.add('/', view)
    app.routes.add('/about', data_view, name='about')
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(FlashMessagesMiddleware, storage='session')

    client = TestClient(app)
    response = client.get('/', allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == [{'category': 'error', 'message': 'Error.'}]


def test_redirect_with_error_and_input() -> None:
    def view() -> RedirectResponse:
        return RedirectResponse('/about').with_error('Error.')

    def data_view(request: Request) -> JSONResponse:
        messages = flash(request).all()
        return JSONResponse(
            {
                'messages': messages,
                'input': request.old_input,
            }
        )

    app = Kupala(
        middleware=[
            Middleware(SessionMiddleware, secret_key='key!', autoload=True),
            Middleware(FlashMessagesMiddleware, storage='session'),
        ]
    )
    app.routes.add('/', view, methods=['post'])
    app.routes.add('/about', data_view, name='about')

    client = TestClient(app)
    response = client.post('/', allow_redirects=True, data={'name': 'invalid'})
    assert response.status_code == 200
    assert response.json() == {
        'messages': [{'category': 'error', 'message': 'Error.'}],
        'input': {'name': 'invalid'},
    }
