import pytest
from starlette.exceptions import HTTPException
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from kupala.application import Kupala
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse, Response
from kupala.testclient import TestClient


def test_handler_by_status_code() -> None:
    async def on_403(request: Request, exc: Exception) -> Response:
        return Response('called')

    async def index_view(request: Request) -> None:
        raise HTTPException(status_code=403)

    app = Kupala(error_handlers={403: on_403})
    app.routes.add('/', index_view)

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
    app.routes.add('/', index_view)

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
    app.routes.add('/', index_view)

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
    app.routes.add('/', index_view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == 'called'


def test_should_reraise_unhandled_exception() -> None:
    class CustomError(TypeError):
        pass

    async def index_view(request: Request) -> None:
        raise CustomError()

    app = Kupala()
    app.routes.add('/', index_view)

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
    app.routes.add('/', HandledExcAfterResponse())

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
    app.routes.add('/', index_view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 409


def test_default_error_handler_for_json() -> None:
    async def view() -> None:
        raise HTTPException(detail='Ooops', status_code=405)

    app = Kupala(debug=False)
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/', headers={'accept': 'application/json'})
    assert response.status_code == 405
    assert response.headers['content-type'] == 'application/json'
    assert response.json() == {
        'message': 'Ooops',
        'errors': {},
    }


def test_default_error_handler_for_json_in_debug() -> None:
    async def view() -> None:
        raise HTTPException(detail='Ooops', status_code=405)

    app = Kupala(debug=True)
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/', headers={'accept': 'application/json'})
    assert response.status_code == 405
    assert response.headers['content-type'] == 'application/json'
    assert response.json() == {
        'message': 'Ooops',
        'errors': {},
        'exception_type': 'starlette.exceptions.HTTPException',
        'exception': "HTTPException(status_code=405, detail='Ooops')",
    }


def test_default_error_handler_not_modified_in_debug() -> None:
    async def view() -> None:
        raise HTTPException(detail='Ooops', status_code=304)

    app = Kupala(debug=True)
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 304


def test_default_error_handler_empty_response_in_debug() -> None:
    async def view() -> None:
        raise HTTPException(detail='Ooops', status_code=204)

    app = Kupala(debug=True)
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 204


def test_default_error_handler_in_debug() -> None:
    async def view() -> None:
        raise HTTPException(detail='Ooops', status_code=500)

    app = Kupala(debug=True)
    app.routes.add('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 500
    assert response.text == 'Ooops'
