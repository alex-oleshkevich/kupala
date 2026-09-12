"""Reflection over callables and type annotations, with no dependency injection concepts."""

import annotationlib
import functools
import inspect
import operator
import types
import typing


def callable_name(fn: typing.Any) -> str:
    """Render a callable as `module.qualname` for error messages."""

    name: str = getattr(fn, "__qualname__", None) or type(fn).__name__
    module: str | None = getattr(fn, "__module__", None)
    return f"{module}.{name}" if module else name


def type_name(key: typing.Any) -> str:
    """Render a type the way a developer wrote it in an annotation."""

    return typing.cast(str, getattr(key, "__qualname__", None) or repr(key))


def is_marked(check: typing.Callable[[typing.Any], bool], fn: typing.Any) -> bool:
    """Apply an `inspect` marker test to a function, or to a callable object's `__call__`."""

    return check(fn) or check(getattr(fn, "__call__", None))  # noqa: B004 - reading a marker, not testing callability


def is_async_callable(fn: typing.Any) -> typing.TypeGuard[typing.Callable[..., typing.Awaitable[typing.Any]]]:
    """Detect coroutine functions, including callable objects with an async `__call__`."""

    return is_marked(inspect.iscoroutinefunction, fn)


def unwrap_alias(annotation: typing.Any) -> typing.Any:
    """Resolve type aliases, including subscripted ones like `Injected[str]`."""

    while True:
        if isinstance(annotation, typing.TypeAliasType):
            annotation = annotationlib.call_evaluate_function(
                annotation.evaluate_value,
                format=annotationlib.Format.FORWARDREF,
            )
            continue

        origin = typing.get_origin(annotation)
        if isinstance(origin, typing.TypeAliasType):
            annotation = unwrap_alias(origin)[typing.get_args(annotation)]
            continue

        return annotation


def unwrap_annotation(annotation: typing.Any) -> tuple[typing.Any, tuple[typing.Any, ...]]:
    """Strip aliases and `Annotated` layers, collecting metadata innermost first."""

    metadata: list[typing.Any] = []
    while True:
        annotation = unwrap_alias(annotation)
        if typing.get_origin(annotation) is not typing.Annotated:
            return annotation, tuple(metadata)

        annotation, *extra = typing.get_args(annotation)
        metadata[:0] = extra


def is_optional(annotation: typing.Any) -> typing.TypeGuard[types.UnionType]:
    """Detect a union that admits `None`."""

    return isinstance(annotation, types.UnionType) and types.NoneType in typing.get_args(annotation)


def strip_none(annotation: typing.Any) -> typing.Any:
    """Drop `None` from a union, leaving the remaining members."""

    args = (arg for arg in typing.get_args(annotation) if arg is not types.NoneType)
    return functools.reduce(operator.or_, args)
