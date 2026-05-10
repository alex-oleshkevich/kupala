import http
import typing

from kupala.requests import Request
from kupala.responses import Response
from kupala.validation import InvalidParam

type SyncExceptionHandler = typing.Callable[[Request, BaseException], Response]
type AsyncExceptionHandler = typing.Callable[[Request, BaseException], typing.Awaitable[Response]]
type ExceptionHandler = SyncExceptionHandler | AsyncExceptionHandler


class KupalaError(Exception): ...


class HTTPError(KupalaError):
    status_code: int = 500
    message: str = http.HTTPStatus.INTERNAL_SERVER_ERROR.phrase

    def __init__(
        self,
        message: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.headers = headers


class BadRequestError(HTTPError):
    status_code = 400
    message = http.HTTPStatus.BAD_REQUEST.phrase


class UnauthorizedError(HTTPError):
    status_code = 401
    message = http.HTTPStatus.UNAUTHORIZED.phrase


class ForbiddenError(HTTPError):
    status_code = 403
    message = http.HTTPStatus.FORBIDDEN.phrase


class NotFoundError(HTTPError):
    status_code = 404
    message = http.HTTPStatus.NOT_FOUND.phrase


class MethodNotAllowedError(HTTPError):
    status_code = 405
    message = http.HTTPStatus.METHOD_NOT_ALLOWED.phrase

    def __init__(
        self,
        *,
        allowed_methods: typing.Sequence[str] | None = None,
        message: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if allowed_methods:
            headers = headers or {}
            headers.update({"allow": ", ".join(allowed_methods)})
        super().__init__(message, headers=headers)


class NotAcceptableError(HTTPError):
    status_code = 406
    message = http.HTTPStatus.NOT_ACCEPTABLE.phrase


class ConflictError(HTTPError):
    status_code = 409
    message = http.HTTPStatus.CONFLICT.phrase


class GoneError(HTTPError):
    status_code = 410
    message = http.HTTPStatus.GONE.phrase


class PayloadTooLargeError(HTTPError):
    status_code = 413
    message = http.HTTPStatus.REQUEST_ENTITY_TOO_LARGE.phrase


class UnsupportedMediaTypeError(HTTPError):
    status_code = 415
    message = http.HTTPStatus.UNSUPPORTED_MEDIA_TYPE.phrase


class ValidationError(HTTPError):
    status_code = 422
    message = http.HTTPStatus.UNPROCESSABLE_ENTITY.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        problem_type: str | None = None,
        errors: typing.Sequence[InvalidParam] = (),
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message, headers=headers)
        self.problem_type = problem_type
        self.errors = list(errors)

    @classmethod
    def for_fields(
        cls,
        fields: dict[str, list[str]],
        message: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> typing.Self:
        invalid_params = [
            InvalidParam(code=None, location=name, reason=err) for name, errs in fields.items() for err in errs
        ]
        return cls(message, errors=invalid_params, headers=headers)

    @classmethod
    def for_field(
        cls,
        name: str,
        errors: list[str],
        message: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> typing.Self:
        return cls(
            message,
            headers=headers,
            errors=[InvalidParam(code=None, location=name, reason=err) for err in errors],
        )


class TooManyRequestsError(HTTPError):
    status_code = 429
    message = http.HTTPStatus.TOO_MANY_REQUESTS.phrase

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
        retry_after: int | None = None,
    ) -> None:
        if retry_after is not None:
            headers = headers or {}
            headers.update({"retry-after": str(retry_after)})
        super().__init__(message, status_code, headers)


class BadGatewayError(HTTPError):
    status_code = 502
    message = http.HTTPStatus.BAD_GATEWAY.phrase


class ServiceUnavailableError(HTTPError):
    status_code = 503
    message = http.HTTPStatus.SERVICE_UNAVAILABLE.phrase


class GatewayTimeoutError(HTTPError):
    status_code = 504
    message = http.HTTPStatus.GATEWAY_TIMEOUT.phrase
