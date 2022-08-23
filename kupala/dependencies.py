import dataclasses

import typing

from kupala.http.requests import Request

_T = typing.TypeVar("_T", covariant=True)


class InjectFactory(typing.Protocol[_T]):
    def __call__(self, request: Request) -> _T:
        ...


@dataclasses.dataclass
class Inject(typing.Generic[_T]):
    factory: InjectFactory[_T]
