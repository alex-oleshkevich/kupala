import datetime
import decimal
import enum
import typing
import uuid

import pytest
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.dependencies import InvalidDependencyError
from kupala.errors import ValidationError
from kupala.params import Query, QueryParam, converter_for, to_bool
from kupala.responses import Response
from kupala.routing import Routes


class Colour(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


def client_for(endpoint: typing.Callable[..., typing.Awaitable[Response]]) -> TestClient:
    """Mount one endpoint at / so a test can drive it over a real request."""

    routes = Routes()
    routes.get("/")(endpoint)
    return TestClient(Kupala("tests", routes=routes), raise_server_exceptions=False)


class TestToBool:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " true "])
    def test_accepts_truthy_spellings(self, value: str) -> None:
        assert to_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "anything"])
    def test_rejects_everything_else(self, value: str) -> None:
        assert to_bool(value) is False


class TestConverterFor:
    @pytest.mark.parametrize(
        "type_", [str, int, float, bool, decimal.Decimal, uuid.UUID, datetime.date, datetime.time, datetime.datetime]
    )
    def test_supports_scalars(self, type_: type) -> None:
        assert converter_for(type_) is not None

    def test_supports_enums(self) -> None:
        assert converter_for(Colour) is Colour

    def test_rejects_everything_else(self) -> None:
        assert converter_for(list[str]) is None


class TestQueryParam:
    def test_reads_a_value(self) -> None:
        async def endpoint(page: Query[int]) -> Response:
            return Response(f"{page!r}")

        with client_for(endpoint) as client:
            assert client.get("/?page=2").text == "2"

    def test_key_defaults_to_the_parameter_name(self) -> None:
        async def endpoint(page: Query[int] = 1) -> Response:
            return Response(f"{page!r}")

        with client_for(endpoint) as client:
            assert client.get("/?page=7").text == "7"

    def test_key_can_be_given_explicitly(self) -> None:
        async def endpoint(page: typing.Annotated[int, QueryParam("p")] = 1) -> Response:
            return Response(f"{page!r}")

        with client_for(endpoint) as client:
            assert client.get("/?p=7").text == "7"
            assert client.get("/?page=7").text == "1"

    def test_returns_the_default_unconverted(self) -> None:
        # the default belongs to the signature, so converting it would turn None into "None"
        async def endpoint(tag: Query[str | None]) -> Response:
            return Response(f"{tag!r}")

        with client_for(endpoint) as client:
            assert client.get("/").text == "None"

    def test_keeps_an_explicit_default(self) -> None:
        async def endpoint(page: Query[int] = 25) -> Response:
            return Response(f"{page!r}")

        with client_for(endpoint) as client:
            assert client.get("/").text == "25"

    def test_reports_a_missing_required_value(self) -> None:
        async def endpoint(page: Query[int]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint) as client:
            http_response = client.get("/")

        assert http_response.status_code == 422
        assert "'page' is required" in http_response.text

    def test_reports_a_value_it_cannot_convert(self) -> None:
        async def endpoint(page: Query[int]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint) as client:
            http_response = client.get("/?page=abc")

        assert http_response.status_code == 422
        assert "must be int" in http_response.text
        # the submitted value must not travel into the response or the logs
        assert "abc" not in http_response.text

    @pytest.mark.parametrize(("query", "expected"), [("flag=true", "True"), ("flag=false", "False")])
    def test_converts_booleans_by_spelling(self, query: str, expected: str) -> None:
        # bool("false") is True, so a query string needs its own rule
        async def endpoint(flag: Query[bool] = False) -> Response:
            return Response(f"{flag!r}")

        with client_for(endpoint) as client:
            assert client.get(f"/?{query}").text == expected

    def test_converts_a_decimal(self) -> None:
        # Decimal signals a bad value with InvalidOperation, which is not a ValueError
        async def endpoint(total: Query[decimal.Decimal]) -> Response:
            return Response(f"{total!r}")

        with client_for(endpoint) as client:
            assert client.get("/?total=10.50").text == "Decimal('10.50')"
            assert client.get("/?total=abc").status_code == 422

    def test_converts_an_enum(self) -> None:
        async def endpoint(colour: Query[Colour]) -> Response:
            return Response(colour.value)

        with client_for(endpoint) as client:
            assert client.get("/?colour=red").text == "red"
            assert client.get("/?colour=green").status_code == 422

    def test_converts_a_date(self) -> None:
        async def endpoint(since: Query[datetime.date]) -> Response:
            return Response(since.isoformat())

        with client_for(endpoint) as client:
            assert client.get("/?since=2026-09-08").text == "2026-09-08"

    def test_rejects_an_unsupported_annotation_at_compile_time(self) -> None:
        async def endpoint(tags: Query[list[str]]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with pytest.raises(InvalidDependencyError) as info:
            client_for(endpoint)

        message = str(info.value)
        assert "cannot be read from a query string" in message
        assert "Annotate it with one of:" in message

    def test_is_a_validation_error(self) -> None:
        assert ValidationError.status_code == 422
