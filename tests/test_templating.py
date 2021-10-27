import typing as t

from kupala.application import Kupala
from kupala.requests import Request
from kupala.responses import Response
from kupala.templating import TemplateResponse
from kupala.testclient import TestClient


class FormatRenderer:
    def render(self, template_name: str, context: t.Mapping = None) -> str:
        return template_name % context


def test_app_renders_templates() -> None:
    app = Kupala(renderer=FormatRenderer())
    assert app.render('hello %(world)s', {'world': 'world'})


def test_calls_context_processors_via_views() -> None:
    def view(request: Request) -> Response:
        return TemplateResponse(request, 'hello %(world)s')

    def context_processor(request: Request) -> dict:
        return {'world': 'world'}

    app = Kupala(renderer=FormatRenderer(), context_processors=[context_processor])
    app.routes.get('/', view)

    client = TestClient(app)
    response = client.get('/')
    assert response.text == 'hello world'
