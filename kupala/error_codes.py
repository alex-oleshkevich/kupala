from __future__ import annotations
import dataclasses
import typing

T = typing.TypeVar("T", default=str, bound=str | int)


@dataclasses.dataclass(frozen=True, slots=True)
class ErrorCode(typing.Generic[T]):
    code: T
    description: str = ''

    def __str__(self) -> str:
        return str(self.description)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str | int):
            return other == self.code

        if not isinstance(other, ErrorCode):
            return NotImplemented

        return bool(self.code == other.code)
