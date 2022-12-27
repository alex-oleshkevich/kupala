from kupala.requests import Request
from kupala.responses import JSONErrorResponse, JSONResponse
from kupala.routing import route
from tests.conftest import ClientFactory


def test_json_error(test_client_factory: ClientFactory) -> None:
    @route("/")
    def view(request: Request) -> JSONResponse:
        return JSONErrorResponse(message="Error", errors={"field": ["error1", "error2"]}, error_code="errcode")

    client = test_client_factory(routes=[view])
    assert client.get("/").json() == {
        "message": "Error",
        "errors": {"field": ["error1", "error2"]},
        "code": "errcode",
    }
