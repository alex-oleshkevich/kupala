import importlib
import os.path
import re
import typing as t

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


def resolve_path(path: str) -> str:
    if not path.startswith('@'):
        return os.path.abspath(path)
    package_name, _, package_path = path.replace('@', '').partition(os.sep)
    package_spec = importlib.import_module(package_name)
    return os.path.join(os.path.dirname(package_spec.__file__), package_path)
