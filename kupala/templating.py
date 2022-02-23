import jinja2
import typing
from starlette.types import Receive, Scope, Send

from kupala.middleware.flash_messages import flash
from kupala.requests import Request
from kupala.responses import Response
from kupala.utils import run_async


class RenderError(Exception):
    """Base class for all renderer classes."""


class JinjaRenderer:
    def __init__(self, env: jinja2.Environment) -> None:
        self._env = env

    def render(self, template_name: str, context: typing.Mapping[str, typing.Any] = None) -> str:
        return self._env.get_template(template_name).render(context or {})


def default_template_variables(request: Request) -> dict:
    return {
        'app': request.app,
        'request': request,
        'url': request.url_for,
        'static': request.static_url,
        'flash_messages': flash(request),
        'form_errors': request.form_errors,
        'old_input': request.old_input,
    }


class TemplateResponse(Response):
    def __init__(
        self,
        template_name: str,
        context: typing.Mapping[str, typing.Any] = None,
        status_code: int = 200,
        media_type: str = 'text/html',
        headers: dict = None,
    ) -> None:
        self.template_name = template_name
        self.context = dict(context or {})

        super().__init__(b'', status_code, headers, media_type)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        context = self.context
        request = Request(scope, receive, send)
        for processor in request.app.context_processors:
            context.update(await run_async(processor, request))
        content = request.app.render(self.template_name, context)

        extensions = request.get("extensions", {})
        if "http.response.template" in extensions:
            await send(
                {
                    "type": "http.response.template",
                    "template": self.template_name,
                    "context": context,
                }
            )
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        await send({"type": "http.response.body", "body": content.encode()})

        if self.background is not None:
            await self.background()
