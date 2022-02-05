import typing

from kupala.requests import Request


class Guard(typing.Protocol):  # pragma: no cover
    def __call__(self, request: Request) -> bool | None | typing.Awaitable[bool | None]:
        ...


def is_authenticated(request: Request) -> bool:
    """Test if user is authenticated."""
    return request.auth.is_authenticated


def has_permission(permission: str) -> Guard:
    """Test if user is has permission."""

    def guard(request: Request) -> bool:
        return request.auth.is_authenticated and permission in request.auth.scopes

    return guard
