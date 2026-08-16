from kupala.errors import BadRequestError, BaseHTTPError


class TestBaseHTTPError:
    def test_subclass_defaults_are_applied(self) -> None:
        error = BadRequestError()

        assert error.detail == "Bad request."
        assert error.title == "Bad request."
        assert error.type == "bad_request_error"
        assert error.status_code == 400
        assert error.headers is None

    def test_explicit_values_are_forwarded_to_http_exception(self) -> None:
        headers = {"X-Error": "custom"}

        error = BaseHTTPError(
            "Custom detail.",
            title="Custom title.",
            type="custom_error",
            status_code=418,
            headers=headers,
        )

        assert error.detail == "Custom detail."
        assert error.title == "Custom title."
        assert error.type == "custom_error"
        assert error.status_code == 418
        assert error.headers == headers
