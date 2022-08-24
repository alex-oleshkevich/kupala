from __future__ import annotations

import jinja2
import typing

from kupala.contracts import TemplateRenderer
from kupala.http.requests import Request

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
