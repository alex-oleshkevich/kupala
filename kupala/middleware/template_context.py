import typing
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.contracts import ContextProcessor
from kupala.requests import Request


class TemplateContextMiddleware:
    """For every request this middleware will call given context processors.
    There return value will be merged and stored in `request.state.template_context` attribute.
    TemplateResponse will merge it with its own context providing a final template context."""

    def __init__(self, app: ASGIApp, context_processors: list[ContextProcessor] = None) -> None:
        self.app = app
        self.context_processors = context_processors or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':  # pragma: nocover
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive, send)
        context: dict[str, typing.Any] = {
            'request': request,
            'config': request.app.config,
            'url': request.url_for,
            'app': request.app,
            'form_errors': request.form_errors,
            'old_input': request.old_input,
        }
        request = Request(scope, receive, send)
        for processor in self.context_processors:
            context.update(processor(request))
        scope['state'].setdefault('template_context', {})
        scope['state']['template_context'].update(context)
        await self.app(scope, receive, send)
