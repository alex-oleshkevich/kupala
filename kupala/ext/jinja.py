import jinja2
import typing as t
from jinja2.ext import Extension

from kupala.application import Kupala
from kupala.container import Resolver
from kupala.contracts import TemplateRenderer
from kupala.providers import Provider


class JinjaRenderer:
    def __init__(self, env: jinja2.Environment) -> None:
        self._env = env

    def render(self, template_name: str, context: t.Mapping = None) -> str:
        return self._env.get_template(template_name).render(context)


class JinjaProvider(Provider):
    def __init__(
        self,
        template_dirs: list[str] = None,
        tests: t.Mapping[str, t.Callable] = None,
        filters: t.Mapping[str, t.Callable] = None,
        globals: t.Mapping[str, t.Any] = None,
        policies: t.Mapping[str, t.Any] = None,
        extensions: t.Sequence[t.Union[str, t.Type[Extension]]] = None,
    ) -> None:
        self.template_dirs = template_dirs or []
        self.filters = filters or {}
        self.globals = globals or {}
        self.tests = tests or {}
        self.policies = dict(policies or {})
        self.extensions = extensions or []

        if 'json.dumps_kwargs' not in self.policies:
            self.policies['json.dumps_kwargs'] = {'ensure_ascii': False, 'sort_keys': True}

    def register(self, app: Kupala) -> None:
        self.template_dirs = [*self.template_dirs, *app.template_dirs]
        app.services.add_singleton(jinja2.Environment, self.make_environment)
        app.services.add_singleton(TemplateRenderer, self.make_renderer)

    def make_renderer(self, resolver: Resolver) -> TemplateRenderer:
        return JinjaRenderer(env=resolver.resolve(jinja2.Environment))

    def make_environment(self, resolver: Resolver) -> jinja2.Environment:
        env = jinja2.Environment(loader=self.make_loader(self.template_dirs), extensions=self.extensions)
        env.filters.update(self.filters)
        env.globals.update(self.globals)
        env.tests.update(self.tests)
        env.policies.update(self.policies)
        return env

    def make_loader(self, template_dirs: list[str]) -> jinja2.BaseLoader:
        directories = []
        packages = []
        for dir_spec in template_dirs:
            if ':' in dir_spec:
                package_name, package_path = dir_spec.split(':')
                if not package_path:
                    package_path = 'templates'
                packages.append([package_name, package_path])
            else:
                directories.append(dir_spec)

        package_loaders = [jinja2.PackageLoader(package_name, package_path) for package_name, package_path in packages]
        if packages and directories:
            return jinja2.ChoiceLoader(
                [
                    *package_loaders,
                    jinja2.FileSystemLoader(directories),
                ]
            )
        if packages:
            return jinja2.ChoiceLoader(package_loaders)
        return jinja2.FileSystemLoader(directories)
