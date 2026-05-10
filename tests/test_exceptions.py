from kupala.exceptions import ValidationError
from kupala.validation import InvalidParam


class TestValidationError:
    def test_for_field(self) -> None:
        error = ValidationError.for_field(
            name="email",
            message="Email is not valid",
            errors=["Email must contain @ character."],
        )
        assert error.status_code == 422
        assert error.message == "Email is not valid"
        assert error.errors == [
            InvalidParam(location="email", reason="Email must contain @ character."),
        ]

    def test_for_field_multiple_errors(self) -> None:
        error = ValidationError.for_field(
            name="password",
            errors=["Password is too short.", "Password must contain a digit."],
        )
        assert error.errors == [
            InvalidParam(location="password", reason="Password is too short."),
            InvalidParam(location="password", reason="Password must contain a digit."),
        ]

    def test_for_fields(self) -> None:
        error = ValidationError.for_fields(
            fields={
                "email": ["Email must contain @ character."],
                "password": ["Password is too short."],
            }
        )
        assert error.status_code == 422
        assert error.errors == [
            InvalidParam(location="email", reason="Email must contain @ character."),
            InvalidParam(location="password", reason="Password is too short."),
        ]

    def test_for_fields_multiple_errors_per_field(self) -> None:
        error = ValidationError.for_fields(
            fields={
                "password": ["Too short.", "Must contain a digit."],
            }
        )
        assert error.errors == [
            InvalidParam(location="password", reason="Too short."),
            InvalidParam(location="password", reason="Must contain a digit."),
        ]

    def test_business_rule_error_has_no_field_errors(self) -> None:
        error = ValidationError("Cannot transfer to your own account")
        assert error.status_code == 422
        assert error.message == "Cannot transfer to your own account"
        assert error.errors == []

    def test_default_message(self) -> None:
        error = ValidationError()
        assert error.status_code == 422
        assert error.message == "Unprocessable Content"

    def test_problem_type(self) -> None:
        error = ValidationError(
            "Cannot transfer to your own account",
            problem_type="urn:problems:kupala:transfer.same-account",
        )
        assert error.problem_type == "urn:problems:kupala:transfer.same-account"

    def test_direct_construction_with_invalid_params(self) -> None:
        params = [
            InvalidParam(location="email", reason="Required.", code="missing"),
            InvalidParam(location="age", reason="Must be >= 18.", code="value_error.gt"),
        ]
        error = ValidationError("Validation failed", errors=params)
        assert error.errors == params

    def test_headers(self) -> None:
        error = ValidationError("nope", headers={"X-Trace-Id": "abc"})
        assert error.headers == {"X-Trace-Id": "abc"}
