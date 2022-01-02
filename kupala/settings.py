import typing as t
from pydantic import BaseSettings

_T = t.TypeVar('_T', bound=BaseSettings)


class BaseConfig(BaseSettings):  # pragma: no cover
    def __enter__(self: _T) -> _T:
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass
