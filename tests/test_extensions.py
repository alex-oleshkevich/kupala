import contextlib
import typing
from starlette.applications import AppType
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient
from unittest import mock

from kupala.applications import Kupala
from kupala.extensions import Extension
from kupala.routing import route


def test_asyngen_extension() -> None:
    start_spy = mock.MagicMock()
    stop_spy = mock.MagicMock()

    class MyExt(Extension):
        @contextlib.asynccontextmanager
        async def bootstrap(self, app: AppType) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
            start_spy(app)
            yield {"key": "value"}
            stop_spy(app)

    @route("/")
    def view(request: Request) -> Response:
        return Response(request.state.key)

    app = Kupala(extensions=[MyExt()], routes=[view])
    with TestClient(app) as client:
        start_spy.assert_called_once_with(app)
        assert client.get("/").text == "value"
    stop_spy.assert_called_once_with(app)
