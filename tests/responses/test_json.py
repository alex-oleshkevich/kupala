import typing as t

from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.json import JSONEncoder
from tests.conftest import TestClientFactory


class CustomObject:
    pass


def _default(o: t.Any) -> t.Any:
    if isinstance(o, CustomObject):
        return '<custom>'


class _JsonEncoder(JSONEncoder):
    def default(self, o: t.Any) -> t.Any:
        return _default(o)


def test_json(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse({'user': 'root'})

    routes.add('/', view)

    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {'user': 'root'}


def test_custom_encoder_class(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse({'object': CustomObject()}, encoder_class=_JsonEncoder)

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.json() == {'object': '<custom>'}


def test_custom_default(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                'object': CustomObject(),
            },
            default=_default,
        )

    routes.add('/', view)
    client = test_client_factory(routes=routes)
    response = client.get('/')
    assert response.json() == {'object': '<custom>'}


def test_json_indents(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> JSONResponse:
        return JSONResponse({'user': {'details': {'name': 'root'}}}, indent=4)

    routes.add('/', view)
    client = test_client_factory(routes=routes)
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
