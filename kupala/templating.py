import jinja2
import typing as t

from kupala.requests import Request

# from kupala.container import BaseProvider, Container


class RenderError(Exception):
    """Base class for all renderer classes."""


class ContextProcessor(t.Protocol):
    def __call__(self, request: Request) -> t.Mapping:
        ...


class EngineAdapter(t.Protocol):
    """Template renderer is a class capable to render
    a template path with a given context."""

    def render(self, template: str, context: dict = None) -> str:
        ...


class JinjaAdapter:
    def __init__(self, env: jinja2.Environment):
        self._env = env

    def render(self, template: str, context: dict = None) -> str:
        tpl = self._env.get_template(template)
        return tpl.render(context)


_context_processors: list[ContextProcessor] = []


def add_context_processor(fn: ContextProcessor) -> None:
    """Register a new context processor."""
    _context_processors.append(fn)


def get_context_processors() -> list[ContextProcessor]:
    """Get all registered context processors."""
    return _context_processors


def context_processor(fn: ContextProcessor) -> ContextProcessor:
    """Register context processor using decorator.

    Example:
        from kupala.templating import context_processor

        @context_processor
        def example_processor(request):
            return {'example': 'data'}
    """

    add_context_processor(fn)
    return fn


class Renderer:
    def __init__(self) -> None:
        self._renderers: dict[str, EngineAdapter] = {}

    def set_renderer(self, ext: str, renderer: EngineAdapter) -> None:
        if not ext.startswith('.'):
            raise ValueError('Extension must start with a dot. For example: ".html".')
        self._renderers[ext] = renderer

    def render(self, template: str, context: dict = None, request: Request = None) -> str:
        """Render a template with context.
        If request argument passed then context processors will be called to provide additional variables."""
        ext = '.' + template.split('.').pop()
        renderer = self._renderers.get(ext)
        if renderer is None:
            raise RenderError('No renderer configured for extension "%s".' % ext)

        context = context or {}
        if request is not None:
            context['request'] = request
            for processor in get_context_processors():
                context.update(processor(request))
        return renderer.render(template, context)


_renderer = Renderer()


def add_renderer(ext: str, renderer: EngineAdapter) -> None:
    get_renderer().set_renderer(ext, renderer)


def get_renderer() -> Renderer:
    return _renderer


def render_to_string(template: str, context: dict = None) -> str:
    return get_renderer().render(template, context)


# class TemplatingProvider(BaseProvider):
#     def __init__(
#             self,
#             env: jinja2.Environment = None, *,
#             template_dirs: list[str] = None,
#             globals: dict[str, t.Any] = None,
#             filters: dict[str, t.Callable] = None,
#             context_processors: list[ContextProcessor] = None,
#             loader: jinja2.BaseLoader = None,
#     ) -> None:
#         assert env or template_dirs, 'Either "env" or "template_dirs" arguments must be set.'
#
#         self._env = env
#         self._loader = loader
#         self._template_dirs = template_dirs or []
#         self._globals = globals or {}
#         self._filters = filters or {}
#         _context_processors.extend(context_processors)
#
#     def bootstrap(self, container: Container) -> None:
#         if self._env:
#             adapter = JinjaAdapter(self._env)
#         else:
#             loader = self._loader or jinja2.FileSystemLoader(self._template_dirs)
#             env = jinja2.Environment(loader=loader)
#             env.globals.update(self._globals)
#             env.filters.update(self._filters)
#             adapter = JinjaAdapter(env)
#         renderer = Renderer()
#         renderer.set_renderer('.html', adapter)
