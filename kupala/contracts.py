import typing as t


class Invoker(t.Protocol):
    """Invoker is an object that can invoke callables resolving and passing dependencies."""

    def invoke(self, fn_or_class: t.Union[t.Callable, t.Type], extra_kwargs: t.Dict[str, t.Any] = None) -> t.Any:
        ...
