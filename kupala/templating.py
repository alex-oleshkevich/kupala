from __future__ import annotations

import inspect
import jinja2
import typing
from starlette.types import Receive, Scope, Send

from kupala.contracts import TemplateRenderer
from kupala.http.requests import Request
from kupala.http.responses import Response

_request_context_processors: list[ContextProcessor] = []


def add_context_processors(*processor: ContextProcessor) -> None:
    _request_context_processors.extend(processor)


def get_context_processors() -> list[ContextProcessor]:
    return _request_context_processors.copy()


class ContextProcessor(typing.Protocol):  # pragma: nocover
    def __call__(self, request: Request) -> typing.Mapping | typing.Awaitable[typing.Mapping]:
        ...


class RenderError(Exception):
    """Base class for all renderer classes."""


class JinjaRenderer(TemplateRenderer):
    def __init__(self, env: jinja2.Environment) -> None:
        self._env = env

    def render(self, template_name: str, context: typing.Mapping[str, typing.Any] = None) -> str:
        return self._env.get_template(template_name).render(context or {})


class TemplateResponse(Response):
    def __init__(
        self,
        template_name: str,
        context: typing.Mapping[str, typing.Any] = None,
        status_code: int = 200,
        media_type: str = "text/html",
        headers: dict[str, str] = None,
    ) -> None:
        self.body = b""
        self.status_code = status_code
        self.template_name = template_name
        self.context = dict(context or {})
        self.background = None
        self._passed_headers = headers
        if media_type is not None:
            self.media_type = media_type

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        context = self.context
        context.update(
            {
                "app": request.app,
                "request": request,
                "url": request.url_for,
                "static": request.app.static_url,
            }
        )
        for processor in get_context_processors():
            if inspect.iscoroutinefunction(processor):
                context.update(await processor(request))  # type: ignore[misc]
            else:
                context.update(processor(request))  # type: ignore[arg-type]

        self.body = request.app.render(self.template_name, context).encode("utf-8")
        self.init_headers(self._passed_headers)

        extensions = request.get("extensions", {})
        if "http.response.template" in extensions:
            await send(
                {
                    "type": "http.response.template",
                    "template": self.template_name,
                    "context": context,
                }
            )
        await super().__call__(scope, receive, send)
