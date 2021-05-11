import importlib
import typing as t


def import_string(dotted_path: t.Any, package: str = None) -> t.Any:
    if not isinstance(dotted_path, str):
        return dotted_path

    # module import?
    if "." not in dotted_path:
        return importlib.import_module(dotted_path, package)

    module_path, attribute = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path, package)
    try:
        return getattr(module, attribute)
    except AttributeError:
        raise ImportError(
            f'Module "{module_path}" does not have attribute "{attribute}"'
        )
