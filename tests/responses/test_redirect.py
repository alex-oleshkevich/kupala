import pytest
from starsessions import SessionMiddleware

from kupala.application import Kupala
from kupala.constants import REDIRECT_INPUT_DATA_SESSION_KEY
from kupala.requests import Request
from kupala.responses import JSONResponse, RedirectResponse
from kupala.testclient import TestClient


def test_redirect() -> None:
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse('/about')

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/', allow_redirects=False)
    assert response.headers['location'] == '/about'


def test_redirect_requires_url_or_path_name() -> None:
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse()

    app = Kupala()
    app.routes.get('/', view)

    with pytest.raises(ValueError) as ex:
        client = TestClient(app)
        client.get('/')
    assert str(ex.value) == 'Either "url" or "path_name" argument must be passed.'


def test_redirect_requires_path_name_requires_request() -> None:
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse(path_name='about')

    app = Kupala()
    app.routes.get('/', view)

    with pytest.raises(ValueError) as ex:
        client = TestClient(app)
        client.get('/')
    assert str(ex.value) == '"path_name" requires "request" argument.'


def test_redirect_requires_input_data_requires_request() -> None:
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse('/about', input_data={'id': 42})

    app = Kupala()
    app.routes.get('/', view)

    with pytest.raises(ValueError) as ex:
        client = TestClient(app)
        client.get('/')
    assert str(ex.value) == '"input_data" requires "request" argument.'


def test_redirect_to_path_name() -> None:
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse(path_name='about', request=request)

    app = Kupala()
    app.routes.get('/', view)
    app.routes.get('/about', view, name='about')

    client = TestClient(app)
    response = client.get('/', allow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == 'http://testserver/about'


def test_redirect_to_path_name_with_path_params() -> None:
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse(path_name='about', path_params={'id': 42}, request=request)

    app = Kupala()
    app.routes.get('/', view)
    app.routes.get('/about/{id}', view, name='about')

    client = TestClient(app)
    response = client.get('/', allow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == 'http://testserver/about/42'


def test_redirect_with_input_data() -> None:
    def view(request: Request) -> RedirectResponse:
        return RedirectResponse('/about', input_data={'id': 42, 'name': 'test'}, request=request)

    def data_view(request: Request) -> JSONResponse:
        return JSONResponse(request.session[REDIRECT_INPUT_DATA_SESSION_KEY])

    app = Kupala()
    app.routes.get('/', view)
    app.routes.get('/about', data_view, name='about')

    app = SessionMiddleware(app, secret_key='key!', autoload=True)
    client = TestClient(app)
    response = client.get('/', allow_redirects=True)
    assert response.status_code == 200
    assert response.json() == {'id': 42, 'name': 'test'}
