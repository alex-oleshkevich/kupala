import pytest
from starlette.exceptions import HTTPException
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket
from starsessions import SessionMiddleware

from kupala.application import Kupala
from kupala.exceptions import BadRequest, ValidationError
from kupala.requests import Request
from kupala.responses import JSONResponse, PlainTextResponse, Response
from kupala.testclient import TestClient


def test_handler_by_status_code() -> None:
    async def on_403(request: Request, exc: Exception) -> Response:
        return Response('called')

    async def index_view(request: Request) -> None:
        raise HTTPException(status_code=403)

    app = Kupala(error_handlers={403: on_403})
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == 'called'


def test_handler_by_type() -> None:
    class CustomError(Exception):
        pass

    async def on_error(request: Request, exc: Exception) -> Response:
        return Response('called')

    async def index_view(request: Request) -> None:
        raise CustomError()

    app = Kupala(error_handlers={CustomError: on_error})
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == 'called'


def test_sync_handler() -> None:
    class CustomError(Exception):
        pass

    def on_error(request: Request, exc: Exception) -> Response:
        return Response('called')

    async def index_view(request: Request) -> None:
        raise CustomError()

    app = Kupala(error_handlers={CustomError: on_error})
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == 'called'


def test_composite_exception() -> None:
    class CustomError(TypeError):
        pass

    def on_error(request: Request, exc: Exception) -> Response:
        return Response('called')

    async def index_view(request: Request) -> None:
        raise CustomError()

    app = Kupala(error_handlers={TypeError: on_error})
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == 'called'


def test_should_reraise_unhandled_exception() -> None:
    class CustomError(TypeError):
        pass

    async def index_view(request: Request) -> None:
        raise CustomError()

    app = Kupala()
    app.routes.get('/', index_view)

    with pytest.raises(CustomError):
        client = TestClient(app)
        response = client.get('/')
        assert response.text == 'called'


class HandledExcAfterResponse:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("OK", status_code=200)
        await response(scope, receive, send)
        raise HTTPException(status_code=406)


def test_handled_exc_after_response() -> None:
    app = Kupala()
    app.routes.get('/', HandledExcAfterResponse())

    with pytest.raises(RuntimeError):
        client = TestClient(app)
        client.get("/")


def test_websocket_should_raise() -> None:
    def raise_runtime_error(request: WebSocket) -> None:
        raise RuntimeError("Oops!")

    app = Kupala()
    app.routes.websocket('/', raise_runtime_error)

    with pytest.raises(RuntimeError):
        client = TestClient(app)
        with client.websocket_connect("/"):
            pass


def test_default_http_error_handler() -> None:
    async def index_view(request: Request) -> None:
        raise HTTPException(status_code=409)

    app = Kupala()
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 409


def test_default_http_validation_error_handler() -> None:
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
            'message': 'Some message.',
            'field_errors': {'field': ['error1']},
        },
    }


def test_default_json_http_error_handler() -> None:
    async def index_view(request: Request) -> None:
        raise BadRequest('Invalid data.')

    app = Kupala()
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/', headers={'Accept': 'application/json'})
    assert response.json() == {
        'message': 'Invalid data.',
        'errors': {},
    }


def test_default_json_http_error_handler_debug_mode() -> None:
    async def index_view(request: Request) -> None:
        raise BadRequest('Invalid data.')

    app = Kupala(debug=True)
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/', headers={'Accept': 'application/json'})
    assert response.json() == {
        'message': 'Invalid data.',
        'errors': {},
        'exception_type': 'kupala.exceptions.BadRequest',
        'exception': "BadRequest(status_code=400, detail='Invalid data.')",
    }


def test_default_json_validation_error_handler() -> None:
    async def index_view(request: Request) -> None:
        raise ValidationError('Invalid data.', {'email': ['Invalid email.']})

    app = Kupala()
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/', headers={'Accept': 'application/json'})
    assert response.json() == {
        'message': 'Invalid data.',
        'errors': {'email': ['Invalid email.']},
    }


def test_default_json_validation_error_handler_debug_mode() -> None:
    async def index_view(request: Request) -> None:
        raise ValidationError('Invalid data.', {'email': ['Invalid email.']})

    app = Kupala(debug=True)
    app.routes.get('/', index_view)

    client = TestClient(app)
    response = client.get('/', headers={'Accept': 'application/json'})
    assert response.json() == {
        'message': 'Invalid data.',
        'errors': {'email': ['Invalid email.']},
    }
