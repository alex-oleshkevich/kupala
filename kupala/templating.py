from __future__ import annotations

import functools
import jinja2
import typing
from jinja2.runtime import Macro
from markupsafe import Markup
from starlette import responses, templating

from kupala.http.requests import Request
from kupala.http.responses import Response


class ContextProcessor(typing.Protocol):  # pragma: nocover
    def __call__(self, request: Request) -> typing.Mapping:
        ...


class _Registry:
    def __init__(self) -> None:
        self.items: dict[str, typing.Callable] = {}

    def update(self, filters: dict[str, typing.Any]) -> None:
        self.items.update(filters)

    def add(self, name: str, callback: typing.Callable) -> None:
        self.items[name] = callback

    def register(self, name: str) -> typing.Callable:
        def inner_decorator(fn: typing.Callable) -> typing.Callable:
            self.add(name, fn)
            return fn

        return inner_decorator

    def keys(self) -> typing.Iterable[str]:
        return self.items.keys()

    def __getitem__(self, item: str) -> typing.Any:
        return self.items[item]

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


class Library:
    def __init__(self) -> None:
        self.filters = _Registry()
        self.tests = _Registry()


class DynamicChoiceLoader(jinja2.ChoiceLoader):
    loaders: list

    def add_loader(self, loader: jinja2.BaseLoader) -> None:
        # don't touch the first loader, this is usually project's template directory
        # also, don't append it because the last loader should be one that loads templates from the framework
        self.loaders.insert(1, loader)


library = Library()


@library.filters.register("nl2br")
def nl2br_filter(value: str) -> str:
    return Markup(value.replace("\n", "<br>"))


def media_url(request: Request, path: str, path_name: str = "media") -> str:
    if any([path.startswith("http://"), path.startswith("https://")]):
        return path
    return request.app.router.url_path_for(path_name, path=path)


def static_url(request: Request, path: str, path_name: str = "static") -> str:
    return request.app.router.url_path_for(path_name, path=path)


def url_matches(request: Request, path_name: str, **path_params: typing.Any) -> bool:
    return request.url_matches(request.app.router.url_path_for(path_name, **path_params))


def default_processors(request: Request) -> dict[str, typing.Any]:
    return {
        "app": request.app,
        "static_url": functools.partial(static_url, request),
        "media_url": functools.partial(media_url, request),
        "url_matches": functools.partial(url_matches, request),
    }


class Jinja2Templates:
    def __init__(self, jinja_env: jinja2.Environment, context_processors: list[ContextProcessor] | None = None) -> None:
        self.jinja_env = jinja_env
        self.context_processors = context_processors or []
        self._templates = templating.Jinja2Templates(directory="templates")
        self._templates.env = jinja_env

    def TemplateResponse(
        self,
        request: Request,
        template_name: str,
        context: dict[str, typing.Any] | None = None,
        *,
        status_code: int = 200,
        headers: dict[str, typing.Any] | None = None,
        content_type: str = "text/html",
    ) -> responses.Response:
        context = context or {}
        context["request"] = request
        for processor in self.context_processors:
            context.update(processor(request))

        return self._templates.TemplateResponse(
            name=template_name,
            context=context,
            status_code=status_code,
            headers=headers,
            media_type=content_type,
        )

    def TemplateBlockResponse(
        self,
        template_name: str,
        block_name: str,
        context: dict[str, typing.Any] | None = None,
        *,
        status_code: int = 200,
        headers: dict[str, typing.Any] | None = None,
        content_type: str = "text/html",
    ) -> Response:
        content = self.render_block_to_string(template_name, block_name, context)
        return Response(content=content, status_code=status_code, headers=headers, content_type=content_type)

    def TemplateMacroResponse(
        self,
        template_name: str,
        macro_name: str,
        macro_kwargs: dict[str, typing.Any] | None = None,
        *,
        status_code: int = 200,
        headers: dict[str, typing.Any] | None = None,
        content_type: str = "text/html",
    ) -> Response:
        content = self.render_macro_to_string(template_name, macro_name, macro_kwargs)
        return Response(content=content, status_code=status_code, headers=headers, content_type=content_type)

    def macro(self, template_name: str, macro_name: str) -> Macro:
        return getattr(self.get_template(template_name).module, macro_name)

    def get_template(self, template_name: str) -> jinja2.Template:
        return self._templates.get_template(template_name)

    def render_to_string(self, template_name: str, context: dict[str, typing.Any] | None = None) -> str:
        template = self.get_template(template_name)
        return template.render(context or {})

    def render_block_to_string(
        self, template_name: str, block_name: str, context: dict[str, typing.Any] | None = None
    ) -> str:
        template = self.get_template(template_name)
        block = template.blocks[block_name]
        block_context = template.new_context(context)
        return "".join(block(block_context))

    def render_macro_to_string(
        self, template_name: str, macro_name: str, macro_kwargs: dict[str, typing.Any] | None = None
    ) -> str:
        macro = self.macro(template_name, macro_name)
        return macro(**(macro_kwargs or {}))
