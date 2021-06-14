import pathlib
import typing as t

import jinja2

from kupala.application import App
from kupala.contracts import TemplateRenderer, URLResolver
from kupala.extensions import Extension
from kupala.requests import Request
from kupala.security.csrf import CSRF_POST_FIELD, csrf_token
from kupala.utils import import_string

ContextProcessor = t.Callable[[Request], dict[str, t.Any]]

JinjaTemplateDirs = t.List[str]


def csrf_input() -> str:
    return '<input name="%s" type="hidden" value="%s">' % (
        CSRF_POST_FIELD,
        csrf_token(),
    )


class JinjaRenderer(TemplateRenderer):
    """A template renderer that uses Jinja2 template engine."""

    def __init__(
        self, env: jinja2.Environment, processors: list[ContextProcessor]
    ) -> None:
        self.env = env
        self.processors = processors

    def render(
        self,
        template_name: str,
        context: dict[str, t.Any] = None,
    ) -> str:
        """Render a template."""
        template = self.env.get_template(template_name)
        context = context or {}
        if "request" in context:
            for processor in self.processors:
                context.update(processor(context["request"]))
        return template.render(context)


class JinjaExtension(Extension):
    def __init__(
        self,
        template_dirs: list[t.Union[str, pathlib.Path]],
        loader: jinja2.loaders.BaseLoader = None,
        filters: dict = None,
        tests: dict = None,
        globals: dict = None,
        extensions: list[str] = None,
        context_processors: list[t.Union[str, ContextProcessor]] = None,
    ) -> None:
        self.loader = loader
        self.dirs = template_dirs
        self.filters = filters or {}
        self.tests = tests or {}
        self.globals = globals or {}
        self.extensions = extensions or []
        self.context_processors = context_processors or []

    def register(self, app: App) -> None:
        app.bind(JinjaTemplateDirs, self.dirs, aliases="jinja.template_dirs")

        app.singleton(jinja2.Environment, self._jinja_factory, aliases="jinja")

        app.singleton(
            JinjaRenderer,
            self._jinja_renderer,
            aliases=["jinja.renderer", TemplateRenderer],
        )

    def _jinja_factory(self, app: App) -> jinja2.Environment:
        if self.loader is None:
            self.loader = jinja2.loaders.ChoiceLoader(
                [
                    jinja2.loaders.FileSystemLoader(list(reversed(self.dirs))),
                ]
            )

        env = jinja2.Environment(
            loader=self.loader,
            extensions=self.extensions,
        )

        env.globals["url"] = app.get(URLResolver).resolve
        env.globals["csrf_input"] = csrf_input
        return env

    def _jinja_renderer(self, env: jinja2.Environment) -> JinjaRenderer:
        processors = [
            import_string(cp) if isinstance(cp, str) else cp
            for cp in self.context_processors
        ]
        return JinjaRenderer(env, processors)
