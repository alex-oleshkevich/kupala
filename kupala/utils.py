from __future__ import annotations

import importlib
import inspect
import os.path
import re
import typing
import typing as t
from starlette.concurrency import run_in_threadpool

CAMEL_TO_SNAKE_PATTERN = re.compile(r'(?<!^)(?=[A-Z])')


def camel_to_snake(name: str) -> str:
    return CAMEL_TO_SNAKE_PATTERN.sub('_', name).lower()


def import_string(path: str, package: str = None) -> t.Any:
    attr = None
    if ':' in path:
        module_name, attr = path.split(':')
    else:
        module_name = path

    module_instance = importlib.import_module(module_name, package)
    if attr:
        return getattr(module_instance, attr)
    return module_instance


def resolve_path(path: t.Union[str, os.PathLike]) -> str:
    path = str(path)
    if not path.startswith('@'):
        return os.path.abspath(path)
    package_name, _, package_path = path.replace('@', '').partition(os.sep)
    package_spec = importlib.import_module(package_name)
    return os.path.join(str(os.path.dirname(str(package_spec.__file__))), package_path)


async def run_async(fn: t.Callable, *args: t.Any, **kwargs: t.Any) -> t.Any:
    """
    Awaits a function.

    Will convert sync to async callable if needed.
    """
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return await run_in_threadpool(fn, *args, **kwargs)


def to_string_list(value: str | t.Iterable[str] | None) -> list[str]:
    """
    Covert string, list, or None to list of strings.

    If value is None then an empty list returned.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


# def fq_name(variable: typing.Any) -> str:
#     module_name = variable.__
