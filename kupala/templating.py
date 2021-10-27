import jinja2
import typing as t

from kupala import responses
from kupala.requests import Request


class RenderError(Exception):
    """Base class for all renderer classes."""


class TemplateRenderer(t.Protocol):  # pragma: nocover
    """Render template to string."""

    def render(self, template_name: str, context: t.Mapping = None) -> str:
        ...


class ContextProcessor(t.Protocol):  # pragma: nocover
    def __call__(self, request: Request) -> t.Mapping:
        ...


class JinjaRenderer:
    def __init__(self, env: jinja2.Environment) -> None:
        self._env = env

    def render(self, template_name: str, context: t.Mapping = None) -> str:
        return self._env.get_template(template_name).render(context)


class TemplateResponse(responses.Response):
    def __init__(
        self,
        request: Request,
        template_name: str,
        context: t.Mapping = None,
        status_code: int = 200,
        media_type: str = 'text/html',
        headers: dict = None,
    ) -> None:
        content = request.app.render(template_name, context)
        super().__init__(content, status_code, headers, media_type)
