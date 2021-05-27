import pathlib
import typing as t

import jinja2

from kupala.application import App
from kupala.contracts import TemplateRenderer, URLResolver
from kupala.extensions import Extension
from kupala.security.csrf import CSRF_POST_FIELD, csrf_token

JinjaTemplateDirs = t.List[str]
JinjaFilters = t.Dict[str, t.Callable]
JinjaTests = t.Dict[str, t.Callable]
JinjaGlobals = t.Dict[str, t.Callable]
JinjaExtensions = t.List[str]


def csrf_input() -> str:
    return '<input name="%s" type="hidden" value="%s">' % (
        CSRF_POST_FIELD,
        csrf_token(),
    )


class JinjaRenderer(TemplateRenderer):
    """A template renderer that uses Jinja2 template engine."""

    def __init__(self, env: jinja2.Environment) -> None:
        self.env = env

    def render(
        self,
        template_name: str,
        context: dict[str, t.Any] = None,
    ) -> str:
        """Render a template."""
        template = self.env.get_template(template_name)
        return template.render(context or {})


class JinjaExtension(Extension):
    def __init__(
        self,
        template_dirs: list[t.Union[str, pathlib.Path]],
        loader: jinja2.loaders.BaseLoader = None,
        filters: dict = None,
        tests: dict = None,
        globals: dict = None,
        extensions: list[str] = None,
    ) -> None:
        self.loader = loader
        self.dirs = template_dirs
        self.filters = filters or {}
        self.tests = tests or {}
        self.globals = globals or {}
        self.extensions = extensions or []

    def register(self, app: App) -> None:
        app.bind(JinjaTemplateDirs, self.dirs, aliases="jinja.template_dirs")
        app.bind(JinjaFilters, self.filters, aliases="jinja.filters")
        app.bind(JinjaTests, self.tests, aliases="jinja.tests")
        app.bind(JinjaGlobals, self.globals, aliases="jinja.globals")
        app.bind(JinjaExtensions, self.extensions, aliases="jinja.extensions")

        def on_env_created(env: jinja2.Environment) -> None:
            env.filters.update(app.get(JinjaFilters))
            env.tests.update(app.get(JinjaTests))
            env.globals.update(app.get(JinjaGlobals))

        app.singleton(
            jinja2.Environment,
            self._jinja_factory,
            aliases="jinja",
        ).after_created(on_env_created)

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
            extensions=app.get(JinjaExtensions),
        )

        env.globals["url"] = app.get(URLResolver).resolve
        env.globals["csrf_input"] = csrf_input
        return env

    def _jinja_renderer(self, env: jinja2.Environment) -> JinjaRenderer:
        return JinjaRenderer(env)
