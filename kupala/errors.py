from starlette.exceptions import HTTPException


class BaseHTTPError(HTTPException):
    detail: str = "The application encountered an unexpected error."
    title: str = "Application error."
    type: str = "error"
    status_code: int = 500
    headers: dict[str, str] | None = None

    def __init__(
        self,
        detail: str | None = None,
        *,
        title: str | None = None,
        type: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.detail = detail or self.detail
        self.title = title or self.title
        self.type = type or self.type
        self.status_code = status_code or self.status_code
        self.headers = headers or self.headers

        super().__init__(
            status_code=self.status_code,
            detail=self.detail,
            headers=self.headers,
        )


class BadRequestError(BaseHTTPError):
    detail: str = "Bad request."
    title: str = "Bad request."
    type: str = "bad_request_error"
    status_code: int = 400


class NotAuthenticatedError(BaseHTTPError):
    detail: str = "Not authenticated."
    title: str = "Authentication error."
    type: str = "authentication_error"
    status_code: int = 401


class NotAuthorizedError(BaseHTTPError):
    detail: str = "Not authorized."
    title: str = "Authorization error."
    type: str = "authorization_error"
    status_code: int = 403


class NotFoundError(BaseHTTPError):
    detail: str = "Not found."
    title: str = "Not found."
    type: str = "not_found_error"
    status_code: int = 404


class MethodNotAllowedError(BaseHTTPError):
    detail: str = "Method not allowed."
    title: str = "Method not allowed."
    type: str = "method_not_allowed_error"
    status_code: int = 405


class RequestTimeoutError(BaseHTTPError):
    detail: str = "Request timed out."
    title: str = "Request timeout."
    type: str = "request_timeout_error"
    status_code: int = 408


class ConflictError(BaseHTTPError):
    detail: str = "Conflict."
    title: str = "Conflict."
    type: str = "conflict_error"
    status_code: int = 409


class GoneError(BaseHTTPError):
    detail: str = "Gone."
    title: str = "Gone."
    type: str = "gone_error"
    status_code: int = 410


class PreconditionFailedError(BaseHTTPError):
    detail: str = "Precondition failed."
    title: str = "Precondition failed."
    type: str = "precondition_failed_error"
    status_code: int = 412


class ContentTooLargeError(BaseHTTPError):
    detail: str = "Content too large."
    title: str = "Content too large."
    type: str = "content_too_large_error"
    status_code: int = 413


class UriTooLongError(BaseHTTPError):
    detail: str = "URI too long."
    title: str = "URI too long."
    type: str = "uri_too_long_error"
    status_code: int = 414


class UnsupportedMediaTypeError(BaseHTTPError):
    detail: str = "Unsupported media type."
    title: str = "Unsupported media type."
    type: str = "unsupported_media_type_error"
    status_code: int = 415


class RangeNotSatisfiableError(BaseHTTPError):
    detail: str = "Range not satisfiable."
    title: str = "Range not satisfiable."
    type: str = "range_not_satisfiable_error"
    status_code: int = 416


class UnprocessableEntityError(BaseHTTPError):
    detail: str = "Unprocessable entity."
    title: str = "Unprocessable entity."
    type: str = "unprocessable_entity_error"
    status_code: int = 422


class ValidationError(BaseHTTPError):
    detail: str = "Validation error."
    title: str = "Validation error."
    type: str = "validation_error"
    status_code: int = 422


class FailedDependencyError(BaseHTTPError):
    detail: str = "Failed dependency."
    title: str = "Failed dependency."
    type: str = "failed_dependency_error"
    status_code: int = 424


class PreconditionRequiredError(BaseHTTPError):
    detail: str = "Precondition required."
    title: str = "Precondition required."
    type: str = "precondition_required_error"
    status_code: int = 428


class RateLimitedError(BaseHTTPError):
    detail: str = "Too many requests."
    title: str = "Rate limited."
    type: str = "rate_limited_error"
    status_code: int = 429


class ThrottledError(BaseHTTPError):
    detail: str = "Request throttled."
    title: str = "Throttled."
    type: str = "throttled_error"
    status_code: int = 429


class InternalServerError(BaseHTTPError):
    detail: str = "The application encountered an unexpected error."
    title: str = "Internal server error."
    type: str = "internal_server_error"
    status_code: int = 500
