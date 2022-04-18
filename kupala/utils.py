from __future__ import annotations

import importlib
import inspect
import re
import typing
from starlette.concurrency import run_in_threadpool

CAMEL_TO_SNAKE_PATTERN = re.compile(r'(?<!^)(?=[A-Z])')


def camel_to_snake(name: str) -> str:
    return CAMEL_TO_SNAKE_PATTERN.sub('_', name).lower()


def import_string(path: str, package: str = None) -> typing.Any:
    attr = None
    if ':' in path:
        module_name, attr = path.split(':')
    else:
        module_name = path

    module_instance = importlib.import_module(module_name, package)
    if attr:
        return getattr(module_instance, attr)
    return module_instance


async def run_async(fn: typing.Callable, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
    """
    Awaits a function.

    Will convert sync to async callable if needed.
    """
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return await run_in_threadpool(fn, *args, **kwargs)


def to_string_list(value: str | typing.Iterable[str] | None) -> list[str]:
    """
    Covert string, list, or None to list of strings.

    If value is None then an empty list returned.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def callable_name(injection: typing.Any) -> str:
    class_name = injection.__name__ if inspect.isclass(injection) else getattr(injection, '__name__', repr(injection))
    module_name = getattr(injection, '__module__', '')
    return f'{module_name}.{class_name}{inspect.signature(injection)}'
