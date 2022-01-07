import jinja2
import typing

from kupala.requests import Request
from kupala.responses import Response


class RenderError(Exception):
    """Base class for all renderer classes."""


class JinjaRenderer:
    def __init__(self, env: jinja2.Environment) -> None:
        self._env = env

    def render(self, template_name: str, context: typing.Mapping[str, typing.Any] = None) -> str:
        return self._env.get_template(template_name).render(context or {})


class TemplateResponse(Response):
    def __init__(
        self,
        request: Request,
        template_name: str,
        context: typing.Mapping[str, typing.Any] = None,
        status_code: int = 200,
        media_type: str = 'text/html',
        headers: dict = None,
    ) -> None:
        full_context = {}
        try:
            full_context.update(request.state.template_context)
        except AttributeError:
            pass

        full_context.update(context or {})
        content = request.app.renderer.render(template_name, full_context)
        super().__init__(content, status_code, headers, media_type)
