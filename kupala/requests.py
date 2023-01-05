from __future__ import annotations

import typing
from starlette.requests import Request, empty_receive, empty_send
from starlette.types import Receive, Scope, Send

_RT = typing.TypeVar("_RT", bound=Request)


def _cached_new(cls: type[Request], scope: Scope, receive: Receive = empty_receive, send: Send = empty_send) -> Request:
    if "request" not in scope:
        instance = object.__new__(cls)
        instance.__init__(scope, receive, send)  # type: ignore
        scope["request"] = instance
    elif scope["request"].__class__ != cls:
        # view function uses custom request class
        request = scope["request"]
        request.__class__ = cls
        scope["request"] = request
    return scope["request"]


class CachedBodyMixin:
    def __new__(cls, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return _cached_new(cls, *args, **kwargs)  # type: ignore


def is_submitted(request: Request) -> bool:
    """Test if request contains submitted form."""
    return request.method.lower() in ["post", "put", "patch", "delete"]


def enforce_cached_body() -> None:
    setattr(Request, "__new__", _cached_new)
