import dataclasses
import typing


@dataclasses.dataclass
class InvalidParam:
    reason: str
    location: str
    code: str | None = None


class ErrorBag:
    def __init__(self, errors: list[InvalidParam] | None = None) -> None:
        self.errors = errors or []

    def add(self, invalid_param: InvalidParam) -> None:
        self.errors.append(invalid_param)

    def append(self, location: str, reason: str, code: str | None = None) -> None:
        self.errors.append(
            InvalidParam(
                location=location,
                reason=reason,
                code=code,
            )
        )

    def __bool__(self) -> bool:
        return len(self.errors) > 0

    def __len__(self) -> int:
        return len(self.errors)

    def __iter__(self) -> typing.Iterator[InvalidParam]:
        return iter(self.errors)
