from __future__ import annotations

import typing

from starlette.exceptions import HTTPException as BaseHTTPException
from starlette import status

from kupala.error_codes import ErrorCode


class KupalaError(Exception):
    """Base class for all exceptions in the application.

    Message precedence:
    1. message argument
    2. error_code.description
    3. self.message
    """

    error_code: ErrorCode | None = None
    message: str | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: ErrorCode | None = None,
    ) -> None:
        error_code = error_code or self.error_code
        error_message = error_code.description if error_code else ""
        self.message = str(message or error_message or self.message)
        self.error_code = error_code
        super().__init__(self.message)


class HTTPException(BaseHTTPException):
    """Base class for all HTTP exceptions in the application."""

    http_code: int | None = None

    def __init__(
        self,
        status_code: int | None = None,
        detail: str | None = None,
        headers: typing.Mapping[str, str] | None = None,
        *,
        error_code: ErrorCode | None = None,
    ) -> None:
        status_code = status_code or self.http_code or status.HTTP_500_INTERNAL_SERVER_ERROR
        self.error_code = error_code
        super().__init__(
            status_code=status_code,
            detail=str(detail) if detail else None,
            headers=headers,
        )


class BadRequest(HTTPException):
    """The request cannot be fulfilled due to bad syntax."""

    http_code = 400


class NotAuthenticated(HTTPException):
    """User is not authenticated."""

    http_code = 401


class NotAuthorized(HTTPException):
    """User has no permissions to perform the action."""

    http_code = 403


class NotFound(HTTPException):
    """Page not found."""

    http_code = 404


class MethodNotAllowed(HTTPException):
    """HTTP method is not allowed for the requested URL."""

    http_code = 405


class NotAcceptable(HTTPException):
    """The server cannot produce a response matching the list of acceptable values."""

    http_code = 406


class RequestTimeout(HTTPException):
    """The server timed out waiting for the request."""

    http_code = 408


class Conflict(HTTPException):
    """A request conflict with the current state of the server."""

    http_code = 409


class UnsupportedMediaType(HTTPException):
    """The server cannot process the request because the payload is in an unsupported format."""

    http_code = 415


class UnprocessableEntity(HTTPException):
    """The server cannot process the request because it is semantically erroneous."""

    http_code = 422

    def __init__(
        self,
        status_code: int | None = None,
        detail: str | None = None,
        headers: typing.Mapping[str, str] | None = None,
        *,
        errors: typing.Mapping[str, typing.Sequence[str]] | None = None,
        error_code: ErrorCode | None = None,
    ) -> None:
        self.errors = errors or {}
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers,
            error_code=error_code,
        )


class ValidatonError(UnprocessableEntity):
    """Raised when validation fails. Same as UnprocessableEntity."""


class TooManyRequests(HTTPException):
    """The client has sent too many requests in a given amount of time."""

    http_code = 429
