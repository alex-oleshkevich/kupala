import functools
import os
import typing

import jinja2
import jinja2.ext
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_babel.contrib.jinja import configure_jinja_env
from starlette_flash import flash

from kupala.extensions import Extension
from kupala.translations import get_language
from kupala.urls import (
    abs_url_for,
    media_url,
    pathname_matches,
    static_url,
    url_matches,
)

type ContextProcessor = typing.Callable[[Request], dict[str, typing.Any]]


class Templates(Jinja2Templates, Extension):
    def __init__(
        self,
        jinja_env: jinja2.Environment | None = None,
        *,
        debug: bool = False,
        auto_escape: bool = True,
        directories: typing.Sequence[str | os.PathLike[str]] = (),
        packages: typing.Sequence[str] = (),
        context_processors: typing.Sequence[ContextProcessor] = (),
        extensions: typing.Sequence[str | type[jinja2.ext.Extension]] = (),
        globals: dict[str, typing.Any] = {},
        filters: dict[str, typing.Callable[[typing.Any], typing.Any]] = {},
        tests: dict[str, typing.Callable[[typing.Any], bool]] = {},
    ) -> None:
        if not jinja_env:
            jinja_env = jinja2.Environment(
                auto_reload=debug,
                autoescape=auto_escape,
                extensions=extensions,
                loader=jinja2.ChoiceLoader(
                    [
                        jinja2.FileSystemLoader(directories),
                        *[jinja2.PackageLoader(package) for package in packages],
                        jinja2.FileSystemLoader("kupala/templates"),
                    ]
                ),
            )
            jinja_env.globals.update(globals)
            jinja_env.filters.update(filters)
            jinja_env.tests.update(tests)
            configure_jinja_env(jinja_env)

        super().__init__(
            env=jinja_env,
            context_processors=list(context_processors),
        )

    def render(self, name: str, context: dict[str, typing.Any] | None = None) -> str:
        template = self.env.get_template(name)
        return template.render(context or {})

    def render_macro(
        self,
        name: str,
        macro: str,
        args: dict[str, typing.Any] | None = None,
    ) -> str:
        template: jinja2.Template = self.env.get_template(name)
        template_module = template.make_module({})
        callback = getattr(template_module, macro)
        return typing.cast(str, callback(**args or {}))

    def render_block(
        self,
        name: str,
        block: str,
        context: dict[str, typing.Any] | None = None,
    ) -> str:
        template = self.env.get_template(name)
        callback = template.blocks[block]
        template_context = template.new_context(context or {})
        return "".join(callback(template_context))

    def render_to_response(
        self,
        request: Request,
        name: str,
        context: dict[str, typing.Any] | None = None,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        return super().TemplateResponse(
            request,
            name,
            context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )


def app_processor(request: Request) -> dict[str, typing.Any]:
    """Add general context to the template."""
    return {
        "app": request.app,
        "url": request.url_for,
        "abs_url": functools.partial(abs_url_for, request),
        "static_url": functools.partial(static_url, request),
        "media_url": functools.partial(media_url, request),
        "url_matches": functools.partial(url_matches, request),
        "pathname_matches": functools.partial(pathname_matches, request),
        "app_language": get_language(),
        "current_user": request.user,
        **(getattr(request.state, "template_context", {})),
    }


def flash_processor(request: Request) -> dict[str, typing.Any]:
    if "session" not in request.scope:
        return {}

    return {"flash_messages": flash(request)}


def auth_processor(request: Request) -> dict[str, typing.Any]:
    if "auth" not in request.scope:
        return {}
    return {"current_user": request.user}
