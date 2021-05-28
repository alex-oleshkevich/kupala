from starlette import exceptions


class HttpException(exceptions.HTTPException):
    """Base exception for HTTP related errors."""

    status_code: int

    def __init__(self, message: str = None) -> None:  # pragma: nocover
        super().__init__(self.status_code, message)


class NotAuthenticatedError(HttpException):
    status_code = 401


class NotAuthorizedError(HttpException):
    status_code = 403


class NotFoundError(HttpException):
    status_code = 404


class MethodNotAllowedError(HttpException):
    status_code = 405


class ConflictError(HttpException):
    status_code = 409
