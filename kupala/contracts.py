import typing as t

SERVICE = t.TypeVar('SERVICE')


class Resolver(t.Protocol):  # pragma: nocover
    """A service resolver protocol."""

    def resolve(self, key: t.Type[SERVICE]) -> SERVICE:
        ...


class Invoker(t.Protocol):  # pragma: nocover
    """Invoker is an object that can invoke callables resolving and passing dependencies."""

    def invoke(self, fn_or_class: t.Union[t.Callable, t.Type], extra_kwargs: t.Dict[str, t.Any] = None) -> t.Any:
        ...
