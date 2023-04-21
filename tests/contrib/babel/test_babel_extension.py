from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.contrib.babel import BabelExtension, Translator
from kupala.routing import route


def test_babel_extension() -> None:
    @route("/")
    def view(request: Request) -> Response:
        return Response(type(request.state.translator).__name__)

    ext = BabelExtension(translation_dirs=[])
    app = Kupala(extensions=[ext], routes=[view])
    with TestClient(app) as client:
        assert client.get("/").text == "Translator"


def test_translator_dependency() -> None:
    @route("/")
    def view(translator: Translator) -> Response:
        return Response(type(translator).__name__)

    ext = BabelExtension(translation_dirs=[])
    app = Kupala(extensions=[ext], routes=[view])
    with TestClient(app) as client:
        assert client.get("/").text == "Translator"
