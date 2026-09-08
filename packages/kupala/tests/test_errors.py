import typing

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from kupala.applications import Kupala
from kupala.errors import BadRequestError, BaseHTTPError, ValidationError
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes
from kupala.websockets import WebSocket, WebSocketError


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

    def test_headers_are_copied_from_the_class_attribute(self) -> None:
        class CustomError(BaseHTTPError):
            headers = {"X-Shared": "1"}  # noqa: RUF012 - a shared mutable default is the point here

        first = CustomError()
        second = CustomError()
        assert first.headers is not None
        first.headers["X-Leaked"] = "yes"

        assert second.headers == {"X-Shared": "1"}
        assert CustomError.headers == {"X-Shared": "1"}

    def test_http_handler_preserves_error_response(self) -> None:
        routes = Routes()

        @routes.get("/error")
        async def endpoint(request: Request) -> Response:
            raise BadRequestError("invalid request", headers={"X-Error": "bad-request"})

        app = Kupala("tests", routes=routes)

        with TestClient(app) as client:
            http_response = client.get("/error")

        assert http_response.status_code == 400
        assert http_response.text == "400: invalid request"
        assert http_response.headers["X-Error"] == "bad-request"
        # a body without a content type is MIME-sniffed, and the detail may echo user input
        assert http_response.headers["content-type"] == "text/plain; charset=utf-8"
        assert http_response.headers["x-content-type-options"] == "nosniff"

    def test_server_error_handler_hides_details_in_production(self) -> None:
        routes = Routes()

        @routes.get("/error")
        async def endpoint(request: Request) -> Response:
            raise RuntimeError("secret")

        for debug, expected_body in (
            (False, "internal server error"),
            (True, "internal server error: secret"),
        ):
            app = Kupala("tests", debug=debug, routes=routes)

            with TestClient(app, raise_server_exceptions=False) as client:
                http_response = client.get("/error")

            assert http_response.status_code == 500
            assert http_response.text == expected_body
            assert http_response.headers["content-type"] == "text/plain; charset=utf-8"
            assert http_response.headers["x-content-type-options"] == "nosniff"

    def test_server_error_handler_can_be_overridden(self) -> None:
        routes = Routes()

        @routes.get("/error")
        async def endpoint(request: Request) -> Response:
            raise RuntimeError("secret")

        async def handler(request: Request, exc: Exception) -> Response:
            return Response("custom handler", status_code=503)

        app = Kupala("tests", routes=routes, error_handlers={Exception: handler})

        with TestClient(app, raise_server_exceptions=False) as client:
            http_response = client.get("/error")

        assert http_response.status_code == 503
        assert http_response.text == "custom handler"

        # an overridden handler must not cost us the re-raise the server logs from
        with TestClient(app) as client, pytest.raises(RuntimeError, match="secret"):
            client.get("/error")

    def test_unhandled_errors_reach_the_server_for_logging(self) -> None:
        routes = Routes()

        @routes.get("/error")
        async def endpoint(request: Request) -> Response:
            raise RuntimeError("secret")

        app = Kupala("tests", routes=routes)

        # ServerErrorMiddleware re-raises after responding; swallowing it would leave crashes
        # entirely unlogged
        with TestClient(app) as client, pytest.raises(RuntimeError, match="secret"):
            client.get("/error")

    def test_websocket_error_handler_closes_with_exception_code(self) -> None:
        routes = Routes()

        @routes.websocket("/socket")
        async def endpoint(websocket: WebSocket) -> None:
            raise WebSocketError(code=4403, reason="denied")

        app = Kupala("tests", routes=routes)

        with TestClient(app) as client, pytest.raises(WebSocketDisconnect) as error:
            client.websocket_connect("/socket").__enter__()

        assert error.value.code == 4403


class TestValidationError:
    def test_carries_no_field_errors_by_default(self) -> None:
        error = ValidationError()

        assert error.detail == "Validation error."
        assert error.status_code == 422
        assert error.errors == {}

    def test_carries_field_errors(self) -> None:
        error = ValidationError("Validation failed.", errors={"email": ["This field is required."]})

        assert error.detail == "Validation failed."
        assert error.errors == {"email": ("This field is required.",)}

    def test_a_lone_message_needs_no_sequence(self) -> None:
        # `str` is a `Sequence[str]` that no type checker rejects, so an unwrapped message must not
        # be iterated into one error per character
        error = ValidationError(errors={"email": "This field is required."})

        assert error.errors == {"email": ("This field is required.",)}

    def test_field_errors_are_detached_from_the_caller(self) -> None:
        messages = ["This field is required."]

        error = ValidationError(errors={"email": messages})
        messages.append("leaked")

        assert error.errors == {"email": ("This field is required.",)}

    def test_field_errors_cannot_be_written_through(self) -> None:
        error = ValidationError(errors={"email": ["This field is required."]})

        # every instance shares the empty default, so a writable map would leak between errors
        with pytest.raises(TypeError):
            typing.cast("dict[str, typing.Sequence[str]]", error.errors)["email"] = []
