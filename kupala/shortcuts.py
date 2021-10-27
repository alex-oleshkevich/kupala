import typing as t

from kupala.application import get_current_application
from kupala.requests import Request
from kupala.response_factories import ResponseFactory


def response(request: Request, status_code: int = 200, headers: dict = None) -> ResponseFactory:
    return ResponseFactory(request, status_code, headers)


def render_to_string(template_name: str, context: t.Mapping = None) -> str:
    app = get_current_application()
    return app.render(template_name, context)
