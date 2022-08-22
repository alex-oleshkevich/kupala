from kupala.http import route
from kupala.http.requests import Request
from kupala.http.responses import JSONErrorResponse, JSONResponse
from tests.conftest import TestClientFactory


def test_json_error(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> JSONResponse:
        return JSONErrorResponse(message="Error", errors={"field": ["error1", "error2"]}, code="errcode")

    client = test_client_factory(routes=[view])
    assert client.get("/").json() == {
        "message": "Error",
        "errors": {"field": ["error1", "error2"]},
        "code": "errcode",
    }
