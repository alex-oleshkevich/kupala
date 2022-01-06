from __future__ import annotations

import typing as t

from kupala.application import Kupala
from kupala.requests import Request

_T = t.TypeVar('_T')


def to_request_injectable(klass: t.Type[_T], factory: t.Callable[[Request], _T]) -> None:
    """Convert regular class into a request injectable."""

    def augmentation(cls: t.Type[_T], request: Request) -> _T:
        return factory(request)

    setattr(klass, 'from_request', classmethod(augmentation))


def to_app_injectable(klass: t.Type[_T], factory: t.Callable[[Kupala], _T]) -> None:
    """Convert regular class into app injectable."""

    def augmentation(cls: t.Type[_T], app: Kupala) -> _T:
        return factory(app)

    setattr(klass, 'from_app', classmethod(augmentation))
