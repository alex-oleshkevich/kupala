import typing as t

from kupala.application import Kupala
from kupala.json import JSONEncoder
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.testclient import TestClient


class CustomObject:
    pass


def _default(o: t.Any) -> t.Any:
    if isinstance(o, CustomObject):
        return '<custom>'
    return o


class _JsonEncoder(JSONEncoder):
    def default(self, o: t.Any) -> t.Any:
        return _default(o)


def test_json() -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse({'user': 'root'})

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {'user': 'root'}


def test_custom_encoder_class() -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse({'object': CustomObject()}, encoder_class=_JsonEncoder)

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.json() == {'object': '<custom>'}


def test_custom_default() -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                'object': CustomObject(),
            },
            default=_default,
        )

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.json() == {'object': '<custom>'}


def test_json_indents() -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse({'user': {'details': {'name': 'root'}}}, indent=4)

    app = Kupala()
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert (
        response.text
        == """{
    "user":{
        "details":{
            "name":"root"
        }
    }
}"""
    )
