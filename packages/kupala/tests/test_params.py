import datetime
import decimal
import enum
import typing
import uuid

import msgspec
import pydantic
import pytest
from starlette.datastructures import FormData, UploadFile
from starlette.testclient import TestClient

from kupala.applications import Kupala
from kupala.binders import DEFAULT_MODEL_BINDERS, ModelBinder
from kupala.dependencies import InvalidDependencyError
from kupala.error_handlers import ErrorHandler
from kupala.errors import ValidationError
from kupala.params import Body, Form, KeyedBinding, Query, QueryParam, converter_for, to_bool
from kupala.requests import Request
from kupala.responses import JSONResponse, Response
from kupala.routing import Routes


class Colour(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


class Filters(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    page: int = 1
    tags: list[str] = pydantic.Field(default_factory=list)


class Credentials(msgspec.Struct):
    login: str
    password: str


class Paging(msgspec.Struct):
    page: int = 1


class PreTypedParam(KeyedBinding):
    """A source whose values arrive already typed, as Starlette's path convertors will deliver them."""

    label = "Path parameter"
    coerce = False


async def show_field_errors(request: Request, exc: Exception) -> Response:
    """The default handler renders only `detail`, so this one puts the field map on the wire."""

    assert isinstance(exc, ValidationError)
    return JSONResponse({field: list(messages) for field, messages in exc.errors.items()}, status_code=422)


def client_for(
    endpoint: typing.Callable[..., typing.Awaitable[Response]],
    *,
    error_handlers: typing.Mapping[type[Exception], ErrorHandler] | None = None,
    model_binders: typing.Sequence[ModelBinder] = DEFAULT_MODEL_BINDERS,
) -> TestClient:
    """Mount one endpoint at / so a test can drive it over a real request."""

    routes = Routes()
    # both methods, so a form or body test can post to the same endpoint a query test gets
    routes.get_or_post("/")(endpoint)
    app = Kupala("tests", routes=routes, error_handlers=error_handlers, model_binders=model_binders)
    return TestClient(app, raise_server_exceptions=False)


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

    def test_a_missing_value_is_reported_per_field(self) -> None:
        async def endpoint(page: Query[int]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.get("/")

        assert http_response.json() == {"page": ["This field is required."]}

    def test_an_unconvertible_value_is_reported_per_field(self) -> None:
        async def endpoint(page: Query[int]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.get("/?page=abc")

        assert http_response.json() == {"page": ["This field must be int."]}
        # the submitted value must not travel into the response or the logs
        assert "abc" not in http_response.text

    def test_field_errors_are_keyed_by_the_name_the_client_sent(self) -> None:
        # the client never saw `page`, so blaming it would send the developer's name back over the wire
        async def endpoint(page: typing.Annotated[int, QueryParam("p")]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.get("/")

        assert http_response.json() == {"p": ["This field is required."]}

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
        assert "cannot be read as a single value" in message
        assert "Annotate it with a model, or one of:" in message


def test_a_source_whose_values_are_not_text_rejects_a_converted_annotation() -> None:
    # `coerce` is False, so no string converter applies however ordinary the annotation looks
    async def endpoint(page: typing.Annotated[int, PreTypedParam()]) -> Response:
        return Response("unreachable")  # pragma: no cover

    with pytest.raises(InvalidDependencyError) as info:
        client_for(endpoint)

    message = str(info.value)
    assert "Path parameter 'page' is annotated int" in message
    assert "Annotate it with a model." in message


class TestQueryModel:
    def test_binds_a_model_from_the_whole_query_string(self) -> None:
        async def endpoint(filters: Query[Filters]) -> Response:
            return JSONResponse(filters.model_dump())

        with client_for(endpoint) as client:
            assert client.get("/?page=2&tags=a&tags=b").json() == {"page": 2, "tags": ["a", "b"]}

    def test_an_absent_sequence_field_keeps_its_default(self) -> None:
        async def endpoint(filters: Query[Filters]) -> Response:
            return JSONResponse(filters.model_dump())

        with client_for(endpoint) as client:
            assert client.get("/").json() == {"page": 1, "tags": []}

    def test_an_unrecognised_key_reaches_the_model(self) -> None:
        # a model that forbids extras can only reject them if every key the client sent is carried over
        async def endpoint(filters: Query[Filters]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.get("/?nonsense=1")

        assert http_response.status_code == 422
        assert "nonsense" in http_response.json()

    def test_reports_validation_failures_per_field(self) -> None:
        async def endpoint(filters: Query[Filters]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.get("/?page=many")

        assert http_response.status_code == 422
        assert list(http_response.json()) == ["page"]

    def test_binds_a_struct(self) -> None:
        # query values are always strings, so a struct bound from one needs its binder's lax path
        async def endpoint(paging: Query[Paging]) -> Response:
            return Response(str(paging.page))

        with client_for(endpoint) as client:
            assert client.get("/?page=2").text == "2"

    def test_rejects_a_model_when_no_binder_is_configured(self) -> None:
        async def endpoint(filters: Query[Filters]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with pytest.raises(InvalidDependencyError, match="cannot be read as a single value"):
            client_for(endpoint, model_binders=())


class TestFormField:
    def test_reads_a_value(self) -> None:
        async def endpoint(name: Form[str]) -> Response:
            return Response(name)

        with client_for(endpoint) as client:
            assert client.post("/", data={"name": "kupala"}).text == "kupala"

    def test_reports_a_missing_required_value(self) -> None:
        async def endpoint(name: Form[str]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.post("/", data={})

        assert http_response.status_code == 422
        assert http_response.json() == {"name": ["This field is required."]}

    def test_keeps_an_explicit_default(self) -> None:
        async def endpoint(name: Form[str] = "anonymous") -> Response:
            return Response(name)

        with client_for(endpoint) as client:
            assert client.post("/", data={}).text == "anonymous"

    def test_rejects_an_upload_where_a_scalar_was_declared(self) -> None:
        # a form carries uploads beside its text fields, and a converter only ever handles strings
        async def endpoint(avatar: Form[str]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.post("/", files={"avatar": ("avatar.png", b"binary")})

        assert http_response.status_code == 422
        assert http_response.json() == {"avatar": ["This field must be str."]}

    def test_binds_a_model_from_the_whole_form(self) -> None:
        async def endpoint(filters: Form[Filters]) -> Response:
            return JSONResponse(filters.model_dump())

        with client_for(endpoint) as client:
            submitted = client.post("/", data={"page": "2", "tags": ["a", "b"]})

        assert submitted.json() == {"page": 2, "tags": ["a", "b"]}

    def test_releases_uploads_when_the_invocation_ends(self) -> None:
        # form data spools uploads to temp files, so every request would leak one without the exit stack
        forms: list[FormData] = []

        async def endpoint(request: Request, name: Form[str]) -> Response:
            forms.append(await request.form())
            return Response(name)

        with client_for(endpoint) as client:
            submitted = client.post("/", data={"name": "kupala"}, files={"avatar": ("a.txt", b"hi")})

        assert submitted.text == "kupala"
        upload = forms[0]["avatar"]
        assert isinstance(upload, UploadFile)
        assert upload.file.closed


class TestJSONBody:
    def test_binds_a_model_from_the_document(self) -> None:
        async def endpoint(credentials: Body[Credentials]) -> Response:
            return Response(credentials.login)

        with client_for(endpoint) as client:
            assert client.post("/", json={"login": "alex", "password": "secret"}).text == "alex"

    def test_a_document_already_carries_its_types(self) -> None:
        # unlike a query string, JSON distinguishes 1 from "1", so nothing is coerced on the way in
        async def endpoint(credentials: Body[Credentials]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.post("/", json={"login": 1, "password": "secret"})

        assert http_response.status_code == 422

    def test_reports_a_body_that_is_not_json(self) -> None:
        async def endpoint(credentials: Body[Credentials]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.post("/", content=b"not json")

        assert http_response.status_code == 422
        assert http_response.json() == {"": ["Expected a JSON document."]}

    def test_reports_validation_failures_per_field(self) -> None:
        async def endpoint(filters: Body[Filters]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with client_for(endpoint, error_handlers={ValidationError: show_field_errors}) as client:
            http_response = client.post("/", json={"page": "many"})

        assert http_response.status_code == 422
        assert list(http_response.json()) == ["page"]

    def test_rejects_a_scalar_annotation_at_compile_time(self) -> None:
        # a body is a document, so kupala does not offer pulling one field out of it
        async def endpoint(page: Body[int]) -> Response:
            return Response("unreachable")  # pragma: no cover

        with pytest.raises(InvalidDependencyError, match="A request body is a document"):
            client_for(endpoint)
