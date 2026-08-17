import typing

import jinja2
from starlette import templating

from kupala.requests import Request
from kupala.responses import Response

type JinjaFilters = dict[str, typing.Callable[..., typing.Any]]
type JinjaGlobals = dict[str, typing.Any]
type JinjaTests = dict[str, typing.Callable[..., bool]]
type JinjaExtensions = typing.Iterable[str]
type ContextProcessor = typing.Callable[[Request], dict[str, typing.Any]]


class RendersToString(typing.Protocol):
    def render(
        self,
        request: Request,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
    ) -> str: ...


class RendersToResponse(typing.Protocol):
    def render_to_response(
        self,
        request: Request,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response: ...


class Templates(RendersToString, RendersToResponse, typing.Protocol): ...  # pragma: no branch


class JinjaTemplates(templating.Jinja2Templates):
    def __init__(
        self,
        env: jinja2.Environment,
        *,
        filters: JinjaFilters | None = None,
        globals: JinjaGlobals | None = None,
        tests: JinjaTests | None = None,
        extensions: JinjaExtensions = (),
        context_processors: typing.Iterable[ContextProcessor] = (),
    ) -> None:
        super().__init__(
            env=env,
            context_processors=list(context_processors),
        )
        if filters is not None:
            self.env.filters.update(filters)
        if globals is not None:
            self.env.globals.update(globals)
        if tests is not None:
            self.env.tests.update(tests)
        for extension in extensions:
            self.env.add_extension(extension)

    def render(
        self,
        request: Request,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
    ) -> str:
        template = self.env.get_template(template_name)
        return template.render(request=request, **(context or {}))

    def render_to_response(
        self,
        request: Request,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        return self.TemplateResponse(
            request,
            template_name,
            context=dict(context) if context else None,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )

    def get_template(self, template_name: str) -> jinja2.Template:
        return self.env.get_template(template_name)

    def render_block(
        self,
        template_name: str,
        block_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
    ) -> str:
        template = self.get_template(template_name)
        template_context = template.new_context(dict(context or {}))
        return "".join(template.blocks[block_name](template_context))

    def render_macro(
        self,
        template_name: str,
        macro_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
    ) -> str:
        template = self.get_template(template_name)
        macro = getattr(template.module, macro_name)
        return str(macro(**(context or {})))
