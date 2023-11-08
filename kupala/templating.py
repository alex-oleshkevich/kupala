from __future__ import annotations

import functools
import jinja2
import time
import typing
from jinja2.runtime import Macro
from starlette import responses, templating
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.datastructures import URL
from starlette.requests import Request

_boot_time = time.time()


class ContextProcessor(typing.Protocol):  # pragma: no cover
    def __call__(self, request: Request) -> typing.Mapping:
        ...


def media_url(request: Request, path: str, path_name: str = "media") -> str:
    if any([path.startswith("http://"), path.startswith("https://")]):
        return path
    return request.app.router.url_path_for(path_name, path=path)


def static_url(request: Request, path: str, path_name: str = "static", append_timestamp: bool = True) -> str:
    url = URL(request.app.router.url_path_for(path_name, path=path))
    if append_timestamp:
        suffix = _boot_time
        if request.app.debug:
            suffix = time.time()
        url = url.include_query_params(ts=suffix)
    return str(url)


def url_for(request: Request, path_name: str, **path_params: typing.Any) -> URL:
    url = request.app.router.url_path_for(path_name, **path_params)
    return url


def abs_url_for(request: Request, path_name: str, **path_params: typing.Any) -> URL:
    return request.url_for(path_name, **path_params)


def url_matches(
    request: Request, path_name: str, path_params: dict[str, str | int] | None = None, exact: bool = False
) -> bool:
    target_url = str(request.app.router.url_path_for(path_name, **(path_params or {})))
    if exact:
        return target_url == request.url.path
    return request.url.path.startswith(target_url)


def app_processor(request: Request) -> dict[str, typing.Any]:
    return {"app": request.app}


def url_processors(request: Request) -> dict[str, typing.Any]:
    return {
        "url": functools.partial(url_for, request),
        "abs_url": functools.partial(abs_url_for, request),
        "static_url": functools.partial(static_url, request),
        "media_url": functools.partial(media_url, request),
        "url_matches": functools.partial(url_matches, request),
    }


class Jinja2Templates(templating.Jinja2Templates):
    """Integrate Jinja templates."""

    def __init__(
        self,
        env: jinja2.Environment,
        context_processors: list[typing.Callable[[Request], dict[str, typing.Any]]] | None = None,
        plugins: list[typing.Callable[[jinja2.Environment], None]] | None = None,
    ) -> None:
        context_processors = context_processors or []

        super().__init__(env=env, context_processors=context_processors)

        for plugin in plugins or []:
            plugin(self.env)

    def macro(
        self, template_name: str, macro_name: str, globals: typing.Mapping[str, typing.Any] | None = None
    ) -> Macro:
        """Return a macros instance from a template."""
        template = self.get_template(template_name)
        module = template.make_module(globals)
        return getattr(module, macro_name)

    def render_to_string(self, template_name: str, context: dict[str, typing.Any] | None = None) -> str:
        """Render template to string."""
        template = self.get_template(template_name)
        return template.render(context or {})

    def render_block_to_string(
        self, template_name: str, block_name: str, context: dict[str, typing.Any] | None = None
    ) -> str:
        """Render template block to string."""
        template = self.get_template(template_name)
        block = template.blocks[block_name]
        block_context = template.new_context(context)
        return "".join(block(block_context))

    def render_macro_to_string(
        self,
        template_name: str,
        macro_name: str,
        macro_kwargs: dict[str, typing.Any] | None = None,
        globals: typing.Mapping[str, typing.Any] | None = None,
    ) -> str:
        """Render template macro to string."""
        macro = self.macro(template_name, macro_name, globals=globals)
        return macro(**(macro_kwargs or {}))

    def TemplateResponse(  # type:ignore[override]
        self,
        request: Request,
        template_name: str,
        context: dict[str, typing.Any] | None = None,
        *,
        status_code: int = 200,
        headers: dict[str, typing.Any] | None = None,
        content_type: str = "text/html",
        background: BackgroundTask | None = None,
    ) -> responses.Response:
        """Render template to HTTP response."""
        return super().TemplateResponse(
            request,
            name=template_name,
            context=context or {},
            status_code=status_code,
            headers=headers,
            media_type=content_type,
            background=background,
        )

    def context_processor(
        self, fn: typing.Callable[[Request], dict[str, typing.Any]]
    ) -> typing.Callable[[Request], dict[str, typing.Any]]:
        """Add a context processor."""
        self.context_processors.append(fn)
        return fn

    def filter(self, name: str = "") -> typing.Callable:
        """Add a new filter to jinja2 environment."""

        def decorator(fn: typing.Callable) -> typing.Callable:
            nonlocal name
            name = name or fn.__name__
            self.env.filters[name] = fn
            return fn

        return decorator

    def test(self, name: str = "") -> typing.Callable:
        """Add a new test to jinja2 environment."""

        def decorator(fn: typing.Callable) -> typing.Callable:
            nonlocal name
            name = name or fn.__name__
            self.env.tests[name] = fn
            return fn

        return decorator

    def setup(self, app: Starlette) -> None:
        """Integrate templates and Starlette app."""
        app.state.templates_dir = self
        app.state.jinja_env = self.env
