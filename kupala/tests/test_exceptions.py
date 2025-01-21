import pytest

from kupala.error_codes import ErrorCode
from kupala.exceptions import (
    BadRequest,
    Conflict,
    HTTPException,
    KupalaError,
    MethodNotAllowed,
    NotAcceptable,
    NotAuthenticated,
    NotAuthorized,
    NotFound,
    RequestTimeout,
    TooManyRequests,
    UnprocessableEntity,
    UnsupportedMediaType,
    ValidatonError,
)


class TestKupalaError:
    def test_simple(self) -> None:
        with pytest.raises(KupalaError, match=""):
            raise KupalaError

    def test_with_message(self) -> None:
        with pytest.raises(KupalaError, match="error"):
            raise KupalaError("error")

    def test_with_error_code_message(self) -> None:
        code = ErrorCode("unknown_error", "Unknown error")
        with pytest.raises(KupalaError, match="Unknown error"):
            raise KupalaError(error_code=code)

    def test_with_message_overrides_error_code(self) -> None:
        code = ErrorCode("unknown_error", "Unknown error")
        with pytest.raises(KupalaError, match="custom error"):
            raise KupalaError("custom error", error_code=code)

    def test_with_message_from_attr(self) -> None:
        class Error(KupalaError):
            message = "Custom error"

        with pytest.raises(KupalaError, match="Custom error"):
            raise Error

    def test_message_from_attr_error_code(self) -> None:
        class Error(KupalaError):
            error_code = ErrorCode("unknown_error", "Unknown error")

        with pytest.raises(KupalaError, match="Unknown error") as ex:
            raise Error
        assert ex.value.error_code == ErrorCode("unknown_error", "Unknown error")

    def test_with_attr_code_override_attr_message(self) -> None:
        class Error(KupalaError):
            message = "Custom error"
            error_code = ErrorCode("unknown_error", "Code error")

        with pytest.raises(KupalaError, match="Code error"):
            raise Error


class TestHTTPError:
    def test_simple(self) -> None:
        exc = HTTPException(400)
        assert exc.status_code == 400
        assert exc.detail == "Bad Request"

    def test_detail(self) -> None:
        exc = HTTPException(400, "Custom error")
        assert exc.status_code == 400
        assert exc.detail == "Custom error"

    def test_headers(self) -> None:
        exc = HTTPException(400, "Custom error", headers={"X-Test": "test"})
        assert exc.status_code == 400
        assert exc.detail == "Custom error"
        assert exc.headers == {"X-Test": "test"}

    def test_error_code(self) -> None:
        code = ErrorCode("unknown_error", "Unknown error")
        exc = HTTPException(400, "Custom error", headers={"X-Test": "test"}, error_code=code)
        assert exc.status_code == 400
        assert exc.error_code == code
        assert exc.detail == "Custom error"
        assert exc.headers == {"X-Test": "test"}

    def test_validation_error(self) -> None:
        exc = ValidatonError(400, errors={"field": ["error"]})
        assert exc.errors == {"field": ["error"]}


@pytest.mark.parametrize(
    "status_code, exc_class, message",
    [
        (400, BadRequest, "Bad Request"),
        (401, NotAuthenticated, "Unauthorized"),
        (403, NotAuthorized, "Forbidden"),
        (404, NotFound, "Not Found"),
        (405, MethodNotAllowed, "Method Not Allowed"),
        (406, NotAcceptable, "Not Acceptable"),
        (408, RequestTimeout, "Request Timeout"),
        (409, Conflict, "Conflict"),
        (415, UnsupportedMediaType, "Unsupported Media Type"),
        (422, UnprocessableEntity, "Unprocessable Content"),
        (422, ValidatonError, "Unprocessable Content"),
        (429, TooManyRequests, "Too Many Requests"),
    ],
)
def test_standard_exceptions(status_code: int, exc_class: type[HTTPException], message: str) -> None:
    exc = exc_class()
    assert exc.status_code == status_code
    assert exc.detail == message
