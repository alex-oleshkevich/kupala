import typing as t

from kupala import responses
from kupala.container import ServiceNotFoundError
from kupala.contracts import TemplateRenderer
from kupala.csrf import get_csrf_input, get_csrf_token
from kupala.messages import FlashBag, flash
from kupala.requests import Request


def default_app_context(request: Request) -> t.Mapping:
    return {
        'debug': request.app.debug,
        'environment': request.app.env,
        'envvar': request.app.dotenv,
        'url': request.url_for,
        'config': request.app.config,
        'form_errors': request.form_errors,
        'old_input': request.old_input,
        'csrf_token': get_csrf_token(request),
        'csrf_input': get_csrf_input(request),
        'messages': flash(request) if 'flash_messages' in request.scope else FlashBag(),
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
            context = context or {}
            full_context = {'request': request}
            renderer: TemplateRenderer = request.app.resolve(TemplateRenderer)
            context_processors = request.app.context_processors
            for context_processor in context_processors:
                full_context.update(context_processor(request))
            full_context = {**full_context, **context}
            content = renderer.render(template_name, full_context)
            super().__init__(content, status_code, headers, media_type)
        except ServiceNotFoundError as ex:
            raise RenderError('A template renderer is not configured for current application.') from ex
