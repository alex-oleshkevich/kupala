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


class Templates:
    def __init__(
        self,
        env: jinja2.Environment | None = None,
        *,
        auto_reload: bool = False,
        packages: typing.Sequence[str] = (),
        directories: typing.Sequence[str] = (),
        filters: JinjaFilters | None = None,
        globals: JinjaGlobals | None = None,
        tests: JinjaTests | None = None,
        extensions: JinjaExtensions = (),
        loaders: typing.Sequence[jinja2.BaseLoader] | None = None,
        context_processors: typing.Iterable[ContextProcessor] = (),
    ) -> None:
        # the list the choice loader reads on every lookup, so `add_loader` needs no rewiring
        self._loaders: list[jinja2.BaseLoader] = list(loaders or ())
        self._loaders.extend(jinja2.PackageLoader(package) for package in packages)
        if directories:
            self._loaders.append(jinja2.FileSystemLoader(directories))

        if env is None:
            self.loader = jinja2.ChoiceLoader(self._loaders)
            # this engine renders HTML, so escaping is the default and opting out is deliberate
            self.env = jinja2.Environment(loader=self.loader, autoescape=True, auto_reload=auto_reload)
        else:
            # keep whatever the caller already configured resolving first, so `packages`,
            # `directories` and `add_loader` extend that environment instead of being ignored
            if env.loader is not None:
                self._loaders.insert(0, env.loader)
            self.loader = jinja2.ChoiceLoader(self._loaders)
            env.loader = self.loader
            self.env = env

        if filters is not None:
            self.env.filters.update(filters)
        if globals is not None:
            self.env.globals.update(globals)
        if tests is not None:
            self.env.tests.update(tests)
        for extension in extensions:
            self.env.add_extension(extension)

        self._responses = templating.Jinja2Templates(
            env=self.env,
            context_processors=list(context_processors),
        )

    def add_loader(self, loader: jinja2.BaseLoader) -> None:
        """Append a loader, so an extension can contribute templates the application may override."""

        self._loaders.append(loader)
        # a template already rendered stays cached under the resolution it had, so drop the cache
        if self.env.cache is not None:
            self.env.cache.clear()

    def render(self, template_name: str, context: typing.Mapping[str, typing.Any] | None = None) -> str:
        template = self.env.get_template(template_name)
        return template.render(context or {})

    def render_to_response(
        self,
        request: Request,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> Response:
        return self._responses.TemplateResponse(
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
