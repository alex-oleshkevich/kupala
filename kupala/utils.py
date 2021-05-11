import importlib
import inspect
import typing as t

from starlette.concurrency import run_in_threadpool


def import_string(dotted_path: t.Any, package: str = None) -> t.Any:
    if not isinstance(dotted_path, str):
        return dotted_path

    # module import?
    if "." not in dotted_path:
        return importlib.import_module(dotted_path, package)

    try:
        module_path, attribute = dotted_path.rsplit(".", 1)
    except ValueError:
        raise ImportError(f"{dotted_path} is a module or not a dotted path.")

    module = importlib.import_module(module_path, package)
    try:
        return getattr(module, attribute)
    except AttributeError:
        raise ImportError(
            f'Module "{module_path}" does not have attribute "{attribute}"'
        )


async def call_as_async(
    fn: t.Callable,
    *args: t.Any,
    **kwargs: t.Any,
) -> t.Any:
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return await run_in_threadpool(fn, *args, **kwargs)


def get_full_class_name(klass: t.Any) -> str:
    """Returns fully qualified class name."""
    return ".".join(
        [
            klass.__class__.__module__.__name__,
            klass.__class__.__name__,
        ]
    )
