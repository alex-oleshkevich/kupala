import typing as t

from kupala import responses
from kupala.container import ServiceNotFoundError
from kupala.contracts import TemplateRenderer
from kupala.requests import Request


def default_app_context(request: Request) -> t.Mapping:
    return {
        'auth': request.auth,
        'user': request.user,
    }


class RenderError(Exception):
    """Base class for all renderer classes."""


class TemplateResponse(responses.Response):
    def __init__(
        self,
        request: Request,
        template_name: str,
        context: t.Dict = None,
        status_code: int = 200,
        media_type: str = 'text/html',
        headers: dict = None,
    ) -> None:
        try:
            full_context = {
                'request': request,
                'config': request.app.config,
                'debug': request.app.debug,
                'url': request.url_for,
                'form_errors': request.form_errors,
                'old_input': request.old_input,
            }
            try:
                full_context.update(request.state.template_context)
            except AttributeError:
                pass

            full_context.update(context or {})
            renderer: TemplateRenderer = request.app.resolve(TemplateRenderer)
            content = renderer.render(template_name, full_context)
            super().__init__(content, status_code, headers, media_type)
        except ServiceNotFoundError as ex:
            raise RenderError('A template renderer is not configured for current application.') from ex
