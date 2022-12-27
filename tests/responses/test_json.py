import typing as t

from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.routing import route
from tests.conftest import ClientFactory


class CustomObject:
    pass


def _default(o: t.Any) -> t.Any:
    if isinstance(o, CustomObject):
        return "<custom>"


def test_json(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> JSONResponse:
        return JSONResponse({"user": "root"})

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"user": "root"}


def test_custom_default(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "object": CustomObject(),
            },
            json_default=_default,
        )

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.json() == {"object": "<custom>"}


def test_json_indents(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> JSONResponse:
        return JSONResponse({"user": {"details": {"name": "root"}}}, indent=4)

    client = test_client_factory(routes=[view])
    response = client.get("/")
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
