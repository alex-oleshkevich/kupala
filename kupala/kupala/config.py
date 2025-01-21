import os
import pathlib
import typing

from starlette.config import Config, undefined

__all__ = ["Config", "is_unittest_environment", "Secrets"]


def is_unittest_environment() -> bool:
    """Test if code executed in unit test environment."""
    return "PYTEST_VERSION" in os.environ


_T = typing.TypeVar("_T")


class Secrets:
    """An interface to access secret variables defined as files."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.directory = pathlib.Path(directory)

    @typing.overload
    def get(
        self,
        key: str,
        default: None = None,
        *,
        cast: None = None,
    ) -> str:  # pragma: no cover
        ...

    @typing.overload
    def get(
        self,
        key: str,
        default: _T,
        *,
        cast: None = None,
    ) -> _T:  # pragma: no cover
        ...

    @typing.overload
    def get(
        self,
        key: str,
        default: None = None,
        *,
        cast: typing.Callable[[str], _T],
    ) -> _T:  # pragma: no cover
        ...

    @typing.overload
    def get(
        self,
        key: str,
        default: _T,
        *,
        cast: typing.Callable[[str], _T],
    ) -> _T:  # pragma: no cover
        ...

    def get(
        self,
        key: str,
        default: typing.Any = undefined,
        *,
        cast: typing.Callable[[str], typing.Any] | None = None,
    ) -> typing.Any:
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
