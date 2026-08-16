import typing

import jinja2

from kupala.requests import Request


class Templates(typing.Protocol):
    def render(
        self, request: Request, template_name: str, context: typing.Mapping[str, typing.Any] | None = None
    ) -> str: ...


class JinjaTemplates:
    def __init__(
        self,
        env: jinja2.Environment,
        *,
        filters: dict[str, typing.Callable[..., typing.Any]] | None = None,
        globals: dict[str, typing.Any] | None = None,
        tests: dict[str, typing.Callable[..., bool]] | None = None,
        extensions: typing.Iterable[str] = (),
    ) -> None:
        self.env = env

    def render(
        self, request: Request, template_name: str, context: typing.Mapping[str, typing.Any] | None = None
    ) -> str:
        template = self.env.get_template(template_name)
        return template.render(request=request, **(context or {}))
