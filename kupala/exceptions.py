import typing as t
from starlette.exceptions import HTTPException as BaseHTTPException


class KupalaError(Exception):
    """Base class for all Kupala framework errors."""


class HTTPException(BaseHTTPException, KupalaError):
    message: t.Optional[str] = None

    def __init__(self, status_code: int, message: str = None) -> None:  # pragma: nocover
        self.message = message or self.message
        super().__init__(status_code=status_code, detail=message)  # type: ignore


class _BasePredefinedHTTPException(HTTPException):
    status_code: int

    def __init__(self, message: str = None) -> None:
        super().__init__(self.status_code, message)


class BadRequest(_BasePredefinedHTTPException):
    """The server cannot or will not process the request due to an apparent client error
    (e.g., malformed request syntax, size too large, invalid request message framing,
    or deceptive request routing)."""

    status_code = 400


class NotAuthenticated(_BasePredefinedHTTPException):
    """Similar to 403 Forbidden, but specifically for use when authentication is required
    and has failed or has not yet been provided."""

    status_code = 401


class PermissionDenied(_BasePredefinedHTTPException):
    """The request contained valid data and was understood by the server, but the server is refusing action.
    This may be due to the user not having the necessary permissions
    for a resource or needing an account of some sort, or attempting a prohibited action
    (e.g. creating a duplicate record where only one is allowed)."""

    status_code = 403


class PageNotFound(_BasePredefinedHTTPException):
    """The requested resource could not be found but may be available in the future.
    Subsequent requests by the client are permissible."""

    status_code = 404


class MethodNotAllowed(_BasePredefinedHTTPException):
    """A request method is not supported for the requested resource; for example,
    a GET request on a form that requires data to be presented via POST, or a PUT request on a read-only resource."""

    status_code = 405


class NotAcceptable(_BasePredefinedHTTPException):
    """The requested resource is capable of generating only content
    not acceptable according to the Accept headers sent in the request."""

    status_code = 406


class Conflict(_BasePredefinedHTTPException):
    """Indicates that the request could not be processed because of conflict in the current state of the resource,
    such as an edit conflict between multiple simultaneous updates."""

    status_code = 409


class UnsupportedMediaType(_BasePredefinedHTTPException):
    """The request entity has a media type which the server or resource does not support. For example,
    the client uploads an image as image/svg+xml, but the server requires that images use a different format."""

    status_code = 415


class UnprocessableEntity(_BasePredefinedHTTPException):
    """Indicates that the server is unwilling to risk processing a request that might be replayed."""

    status_code = 422


class TooManyRequests(_BasePredefinedHTTPException):
    """The user has sent too many requests in a given amount of time. Intended for use with rate-limiting schemes."""

    status_code = 429


class ValidationError(KupalaError):
    """Raised when data is not valid by any criteria."""

    def __init__(
        self,
        message: str = None,
        errors: t.Mapping[str, list[str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}
