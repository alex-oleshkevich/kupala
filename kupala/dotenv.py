import builtins
import functools
import os
import typing as t

import dotenv as dotenvlib

from . import json


def noop_coerce(x: t.Any) -> None:
    return x


class Undefined:
    def __bool__(self) -> bool:
        return False


_undefined = Undefined()


class DotenvError(Exception):
    pass


class VariableNotFound(DotenvError, KeyError):
    """Raised when a variable is missing in the container."""


def bool_cast(value: str) -> bool:
    _positives = ["1", "yes", "true", "on"]
    _negatives = ["0", "no", "false", "off"]
    value = str(value).lower().strip()
    if value in _positives:
        return True

    if value in _negatives:
        return False

    raise DotenvError(f'Cannot cast string "{value}" to boolean value.')


def file_cast(value: str, binary: bool = False) -> t.Union[str, bytes]:
    """Reads file as blob."""
    if not os.path.isfile(value):
        raise DotenvError(f'The value "{value}" is not a file.')

    mode = "rb" if binary else "r"
    with open(value, mode) as f:
        return f.read()


def list_(
    value: t.Union[str, t.Iterable],
    coerce: t.Callable[[str], t.Any] = noop_coerce,
    split_char: str = " ",
) -> list[t.Any]:
    if isinstance(value, str):
        values = map(str.strip, value.split(split_char))
        return list(
            map(
                coerce,
                map(
                    lambda x: x.strip("\"'"),
                    values,
                ),
            )
        )
    return list(value)


class Env:
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix
        self._values = os.environ.copy()

    def load(self, dot_file: str) -> str:
        """Load .env file."""
        dot_path = dotenvlib.find_dotenv(str(dot_file))
        self._import(dotenvlib.dotenv_values(dot_path))
        return dot_path

    def _import(self, values: t.Mapping[str, str]) -> None:
        for key, value in values.items():
            if key.startswith(self.prefix):
                offset = 0
                if len(self.prefix):
                    offset = 1
                self._values[key[len(self.prefix) + offset :]] = value

    def all(self) -> dict:
        """Return all environmental value."""
        return self._values

    def str(self, name: str, default: t.Union[str, Undefined] = _undefined) -> str:
        """Get a variable as a string."""
        return self.get(name, default, str)

    def bytes(
        self,
        name: builtins.str,
        default: t.Union[bytes, Undefined] = _undefined,
        encoding: builtins.str = "utf8",
    ) -> bytes:
        """Get a variable as bytes."""
        value = self.get(name, default)
        if hasattr(value, "encode"):
            value = value.encode(encoding)
        return bytes(value)

    def int(
        self,
        name: builtins.str,
        default: t.Union[int, Undefined] = _undefined,
    ) -> int:
        """Get a variable as an integer."""
        return self.get(name, default, int)

    def float(
        self,
        name: builtins.str,
        default: t.Union[float, Undefined] = _undefined,
    ) -> float:
        """Get a variable as a float."""
        return self.get(name, default, float)

    def bool(
        self,
        name: builtins.str,
        default: t.Union[bool, Undefined] = False,
    ) -> bool:
        """Get a variable as a boolean value."""
        value = self.get(name, None)
        if value is None:
            return default if isinstance(default, bool) else False
        return value.lower() in ["yes", "y", "1"]

    def list(
        self,
        name: builtins.str,
        default: t.Union[list[t.Any], Undefined] = None,
        coerce: t.Callable[[builtins.str], t.Any] = noop_coerce,
        split_char: builtins.str = ",",
    ) -> builtins.list[t.Any]:
        """Get a list from the environment variables.
        Use `coerce` function to cast each item to a specific type.
        You can set a different separator using `split_char` argument."""
        caster = functools.partial(list_, coerce=coerce, split_char=split_char)
        return self.get(name, default, caster)

    def csv(
        self,
        name: builtins.str,
        default: t.Union[builtins.list[t.Any], Undefined] = _undefined,
        coerce: t.Callable[[builtins.str], t.Any] = noop_coerce,
        delimiter: builtins.str = ",",
    ) -> builtins.list[t.Any]:
        """Parse a CSV string into list from the environment variable.
        Use `coerce` function to cast each item to a specific type."""
        caster = functools.partial(list_, coerce=coerce, split_char=delimiter)
        return self.get(name, default, caster)

    def json(
        self,
        name: builtins.str,
        default: t.Union[t.Any, Undefined] = _undefined,
    ) -> t.Any:
        """Decode JSON string from the environment variable."""
        value = self.get(name, default)
        if isinstance(value, str):
            return json.loads(value)
        return default

    def file(
        self,
        name: builtins.str,
        default: t.Union[t.AnyStr, Undefined] = _undefined,
        binary: builtins.bool = False,
    ) -> t.AnyStr:
        """Read a file contents using the path
        defined by the environment variable."""
        cast = functools.partial(file_cast, binary=binary)
        try:
            return self.get(name, _undefined, cast)
        except DotenvError:
            if isinstance(default, Undefined):
                raise
            return default

    def get(
        self,
        name: builtins.str,
        default: t.Union[t.Any, Undefined] = _undefined,
        cast: t.Callable[[t.Any], t.Any] = None,
    ) -> t.Any:
        """Get an environment variable.
        Use `cast` callable to convert a value to a specific type."""
        value = self._values.get(name, default)
        if value == _undefined:
            raise VariableNotFound(
                f'Environment variable "{name}" was not set '
                f"and has no default value."
            ) from None
        if cast is not None:
            value = cast(value)
        return value

    def set(self, name: builtins.str, value: builtins.str) -> None:
        """Set an environment variable.
        Note, it won't set a global variable
        but will update local variable cache."""
        self._values[name] = str(value)

    def delete(self, name: builtins.str) -> None:
        """Delete a variable from the local cache."""
        del self._values[name]

    __call__ = str
    __getitem__ = get
    __setitem__ = set
    __delitem__ = delete

    def __repr__(self) -> builtins.str:
        return "<Env: %s>" % {k: v for k, v in self.all().items()}

    def __contains__(self, item: builtins.str) -> builtins.bool:
        return item in self._values
