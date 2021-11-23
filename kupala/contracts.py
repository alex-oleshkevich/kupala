import typing as t

from kupala.requests import Request

SERVICE = t.TypeVar('SERVICE')


class PasswordHasher(t.Protocol):  # pragma: no cover
    def hash(self, plain_password: str) -> str:
        ...


class PasswordVerifier(t.Protocol):  # pragma: no cover
    def verify(self, plain: str, hashed: str) -> bool:
        ...


class Resolver(t.Protocol):  # pragma: nocover
    """A service resolver protocol."""

    def resolve(self, key: t.Type[SERVICE]) -> SERVICE:
        ...


class Invoker(t.Protocol):  # pragma: nocover
    """Invoker is an object that can invoke callables resolving and passing dependencies."""

    def invoke(self, fn_or_class: t.Union[t.Callable, t.Type], extra_kwargs: t.Dict[str, t.Any] = None) -> t.Any:
        ...


class TemplateRenderer(t.Protocol):  # pragma: nocover
    """Render template to string."""

    def render(self, template_name: str, context: t.Dict = None) -> str:
        ...


class ContextProcessor(t.Protocol):  # pragma: nocover
    def __call__(self, request: Request) -> t.Mapping:
        ...
