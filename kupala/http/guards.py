import typing

from kupala.http.exceptions import NotAuthenticated
from kupala.http.requests import Request


class Guard(typing.Protocol):  # pragma: no cover
    def __call__(self, request: Request) -> bool | None | typing.Awaitable[bool | None]:
        ...


def is_authenticated(request: Request) -> None:
    """Test if user is authenticated."""
    if not request.auth.is_authenticated:
        raise NotAuthenticated()


def has_permission(permission: str) -> Guard:
    """Test if user is has permission."""

    def guard(request: Request) -> bool:
        return request.auth.is_authenticated and permission in request.auth.scopes

    return guard
