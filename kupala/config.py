import os
import pathlib
import typing

_T = typing.TypeVar("_T")
undefined = object()


class Secrets:
    """An interface to access secret variables defined as files."""

    def __init__(self, directory: str | os.PathLike) -> None:
        self.directory = pathlib.Path(directory)

    @typing.overload
    def get(
        self, key: str, default: typing.Any = undefined, *, cast: typing.Callable[[str], _T]
    ) -> _T:  # pragma: no cover
        ...

    @typing.overload
    def get(
        self, key: str, default: typing.Any = undefined, *, cast: typing.Callable[[str], str] | None = None
    ) -> str:  # pragma: no cover
        ...

    def get(
        self, key: str, default: typing.Any = undefined, *, cast: typing.Callable[[str], str | _T] | None = None
    ) -> str | _T:
        file_name = pathlib.Path(self.directory / key)
        if not file_name.exists():
            if default == undefined:
                raise FileNotFoundError(f"Secret file missing and no default value provided: {file_name}.")
            return default
        value = file_name.read_text()
        if cast:
            return cast(value)
        return value

    __call__ = get
