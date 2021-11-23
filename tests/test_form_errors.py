from starsessions import SessionMiddleware

from kupala.application import Kupala
from kupala.exceptions import ValidationError
from kupala.form_errors import FormErrorsMiddleware
from kupala.messages import FlashMessagesMiddleware
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.testclient import TestClient


def test_http_form_errors() -> None:
    """When ValidationError is raised by a view handler, the request should be redirected to the previous page
    (determined by Referer headers) with current form data (except files) and validation error messages."""

    async def render_form_view(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                'old_input': request.old_input,
                'form_errors': request.form_errors,
            }
        )

    async def submit_form_view() -> None:
        raise ValidationError('Some message.', {'field': ['error1']})

    app = Kupala()
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(FlashMessagesMiddleware)
    app.middleware.use(FormErrorsMiddleware)
    app.routes.get('/render', render_form_view)
    app.routes.post('/submit', submit_form_view)

    client = TestClient(app)
    response = client.post(
        '/submit',
        data={'key': 'value'},
        headers={'Referer': 'http://testserver/render'},
        allow_redirects=True,
    )

    assert response.json() == {
        'old_input': {'key': 'value'},
        'form_errors': {
            'field_errors': {'field': ['error1']},
        },
    }


def test_json_form_errors() -> None:
    async def index_view(request: Request) -> None:
        raise ValidationError('Invalid data.', {'email': ['Invalid email.']})

    app = Kupala()
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(FlashMessagesMiddleware)
    app.middleware.use(FormErrorsMiddleware)
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/', headers={'Accept': 'application/json'})
    assert response.json() == {
        'message': 'Invalid data.',
        'errors': {'email': ['Invalid email.']},
    }


def test_json_form_errors_debug_mode() -> None:
    async def index_view(request: Request) -> None:
        raise ValidationError('Invalid data.', {'email': ['Invalid email.']})

    app = Kupala(debug=True)
    app.middleware.use(SessionMiddleware, secret_key='key!', autoload=True)
    app.middleware.use(FlashMessagesMiddleware)
    app.middleware.use(FormErrorsMiddleware)
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/', headers={'Accept': 'application/json'})
    assert response.json() == {
        'message': 'Invalid data.',
        'errors': {'email': ['Invalid email.']},
    }