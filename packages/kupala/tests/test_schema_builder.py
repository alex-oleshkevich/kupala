import collections.abc
import enum
import types
import typing

import pydantic
import pytest
from starlette.convertors import Convertor
from starlette.types import Receive, Scope, Send

from kupala.params import Body, Form, Query, QueryParam
from kupala.requests import Request
from kupala.responses import JSONResponse, Response
from kupala.routing import RouteDefinition, Routes
from kupala.schema import openapi
from kupala.schema.builder import (
    DuplicateOperationError,
    OpenAPIBuilder,
    UnsupportedSchemaError,
    _rewrite_refs,
    _split_library_schema,
    build_document,
    convertor_schema,
    default_schema_namer,
    documented_methods,
    merge_responses,
    path_parameters,
)
from kupala.schema.responses import parse_response
from kupala.websockets import WebSocket

DOCUMENT = openapi.OpenAPI(info=openapi.Info(title="Test", version="1"))


async def view(request: Request) -> Response:
    return Response("ok")  # pragma: no cover


def definition(*methods: str) -> RouteDefinition:
    return RouteDefinition(path="/", fn=view, name=None, methods=methods, middleware=())


class TestPathParameters:
    def test_rewrites_a_converted_variable_as_a_plain_one(self) -> None:
        template, parameters = path_parameters("/users/{id:int}/posts/{slug}")

        assert template == "/users/{id}/posts/{slug}"
        assert [parameter.name for parameter in parameters] == ["id", "slug"]
        assert all(parameter.required for parameter in parameters)
        assert all(parameter.in_ is openapi.ParameterLocation.PATH for parameter in parameters)

    def test_a_path_without_variables_declares_none(self) -> None:
        assert path_parameters("/users") == ("/users", ())

    @pytest.mark.parametrize(
        ("path", "schema"),
        [
            ("/{value:str}", {"type": "string"}),
            ("/{value:int}", {"type": "integer"}),
            ("/{value:float}", {"type": "number"}),
            ("/{value:uuid}", {"type": "string", "format": "uuid"}),
            ("/{value:path}", {"type": "string", "format": "path"}),
        ],
    )
    def test_carries_what_the_convertor_guarantees(self, path: str, schema: openapi.Schema) -> None:
        _, parameters = path_parameters(path)

        assert parameters[0].schema == schema


class TestConvertorSchema:
    def test_an_unknown_convertor_is_described_as_a_string(self) -> None:
        class WeekdayConvertor(Convertor[str]):
            regex = "[a-z]+"

            def convert(self, value: str) -> str:
                return value  # pragma: no cover

            def to_string(self, value: str) -> str:
                return value  # pragma: no cover

        assert convertor_schema(WeekdayConvertor()) == {"type": "string"}


class TestDocumentedMethods:
    def test_drops_the_head_that_comes_free_with_a_get(self) -> None:
        assert documented_methods(definition("GET", "HEAD")) == ("get",)

    def test_keeps_a_head_asked_for_on_its_own(self) -> None:
        assert documented_methods(definition("HEAD")) == ("head",)

    def test_collapses_a_repeated_method(self) -> None:
        assert documented_methods(definition("POST", "POST")) == ("post",)


class TestBuildDocument:
    def test_names_a_path_by_the_group_that_encloses_it(self) -> None:
        routes = Routes(prefix="/api", namespace="api")
        group = routes.group("/v1", namespace="v1")
        group.get("/users", name="index")(view)

        paths = build_document(routes, DOCUMENT).paths or {}

        assert list(paths) == ["/api/v1/users"]
        assert paths["/api/v1/users"].get is not None
        assert paths["/api/v1/users"].get.operation_id == "api.v1.index"

    def test_omits_a_route_kept_out_of_the_schema(self) -> None:
        # `describe` reports the whole tree, so this filter is the generator's own
        routes = Routes()
        routes.get("/public")(view)
        routes.get("/private", include_in_schema=False)(view)

        assert list(build_document(routes, DOCUMENT).paths or {}) == ["/public"]

    def test_omits_what_it_cannot_describe(self) -> None:
        async def legacy(scope: Scope, receive: Receive, send: Send) -> None: ...  # pragma: no cover

        async def socket(websocket: WebSocket) -> None: ...  # pragma: no cover

        routes = Routes()
        routes.get("/users")(view)
        routes.websocket("/ws")(socket)
        routes.mount("/legacy", legacy)
        routes.host("cdn.example.com", legacy)

        assert list(build_document(routes, DOCUMENT).paths or {}) == ["/users"]

    def test_replaces_whatever_paths_the_document_carried(self) -> None:
        routes = Routes()
        routes.get("/users")(view)

        document = build_document(routes, DOCUMENT)

        assert document.info is DOCUMENT.info
        assert list(document.paths or {}) == ["/users"]

    def test_names_an_operation_after_its_route(self) -> None:
        routes = Routes()
        routes.get("/users", name="users.index")(view)

        paths = build_document(routes, DOCUMENT).paths or {}

        assert paths["/users"].get is not None
        assert paths["/users"].get.operation_id == "users.index"

    def test_one_route_answering_several_methods_names_each_operation(self) -> None:
        routes = Routes()
        routes.get_or_post("/search", name="search")(view)

        paths = build_document(routes, DOCUMENT).paths or {}
        item = paths["/search"]

        assert item.get is not None
        assert item.post is not None
        assert (item.get.operation_id, item.post.operation_id) == ("search_get", "search_post")

    def test_an_author_given_id_is_kept(self) -> None:
        routes = Routes()
        routes.get("/users", name="users.index", operation_id="listUsers")(view)

        paths = build_document(routes, DOCUMENT).paths or {}

        assert paths["/users"].get is not None
        assert paths["/users"].get.operation_id == "listUsers"

    def test_an_author_given_id_is_split_across_the_methods_it_names(self) -> None:
        # without the suffix the author's own id collides with itself, and the error would tell them to
        # pass the `operation_id=` they already passed
        routes = Routes()
        routes.get_or_post("/search", operation_id="search")(view)

        paths = build_document(routes, DOCUMENT).paths or {}
        item = paths["/search"]

        assert item.get is not None
        assert item.post is not None
        assert (item.get.operation_id, item.post.operation_id) == ("search_get", "search_post")

    def test_two_routes_that_document_the_same_path_are_refused(self) -> None:
        # the documented path drops the convertor, so these route apart but describe the same operation
        routes = Routes()
        routes.get("/users/{key:int}", name="by_id")(view)
        routes.get("/users/{key}", name="by_slug")(view)

        with pytest.raises(DuplicateOperationError, match=r"both describe GET /users/\{key\}"):
            build_document(routes, DOCUMENT)

    def test_a_method_no_path_item_models_is_named(self) -> None:
        routes = Routes()
        routes.add("/x", view, methods=["REPORT"], openapi=openapi.Operation())

        with pytest.raises(ValueError, match="describe no 'report' operation"):
            build_document(routes, DOCUMENT)

    def test_two_operations_cannot_share_an_id(self) -> None:
        routes = Routes()
        routes.get("/users", operation_id="same")(view)
        routes.get("/posts", operation_id="same")(view)

        with pytest.raises(DuplicateOperationError, match="'same' describes both"):
            build_document(routes, DOCUMENT)

    def test_an_authored_parameter_joins_the_ones_the_path_declares(self) -> None:
        trace = openapi.Parameter(name="x-trace", in_=openapi.ParameterLocation.HEADER)
        routes = Routes()
        routes.get("/users/{id:int}", parameters=[trace])(view)

        paths = build_document(routes, DOCUMENT).paths or {}
        described = paths["/users/{id}"].get
        assert described is not None

        names = [typing.cast(openapi.Parameter, parameter).name for parameter in described.parameters or ()]
        assert names == ["id", "x-trace"]

    def test_an_authored_parameter_survives_a_path_without_variables(self) -> None:
        trace = openapi.Parameter(name="x-trace", in_=openapi.ParameterLocation.HEADER)
        routes = Routes()
        routes.get("/users", parameters=[trace])(view)

        paths = build_document(routes, DOCUMENT).paths or {}
        described = paths["/users"].get
        assert described is not None

        assert described.parameters == (trace,)

    def test_an_author_may_replace_a_parameter_the_path_declares(self) -> None:
        # a document cannot carry two parameters of one name and location, so the author's wins
        described_id = openapi.Parameter(
            name="id",
            in_=openapi.ParameterLocation.PATH,
            required=True,
            description="The user's id.",
            schema={"type": "integer", "minimum": 1},
        )
        routes = Routes()
        routes.get("/users/{id:int}", parameters=[described_id])(view)

        paths = build_document(routes, DOCUMENT).paths or {}
        described = paths["/users/{id}"].get
        assert described is not None

        assert described.parameters == (described_id,)

    def test_an_authored_response_replaces_the_default(self) -> None:
        routes = Routes()
        routes.get("/users", responses={"204": openapi.Response(description="Nothing.")})(view)

        paths = build_document(routes, DOCUMENT).paths or {}

        assert paths["/users"].get is not None
        assert paths["/users"].get.responses == {"204": openapi.Response(description="Nothing.")}

    def test_an_operation_that_documents_no_response_still_declares_one(self) -> None:
        routes = Routes()
        routes.get("/users")(view)

        paths = build_document(routes, DOCUMENT).paths or {}

        assert paths["/users"].get is not None
        assert list(paths["/users"].get.responses or {}) == ["200"]

    def test_two_routes_on_one_path_share_a_path_item(self) -> None:
        routes = Routes()
        routes.get("/users/{id:int}", name="show")(view)
        routes.delete("/users/{id:int}", name="destroy")(view)

        paths = build_document(routes, DOCUMENT).paths or {}
        item = paths["/users/{id}"]

        assert item.get is not None
        assert item.delete is not None
        assert typing.cast(openapi.Parameter, (item.get.parameters or ())[0]).name == "id"


class Filters(pydantic.BaseModel):
    page: int = 1
    tags: list[str] = []


class User(pydantic.BaseModel):
    name: str


class UserHeaders(typing.TypedDict, total=False):
    XRequestId: str


class TestContributions:
    def test_a_query_parameter_is_taken_from_the_signature(self) -> None:
        async def search(request: Request, q: Query[str]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.get("/search")(search)
        described = (build_document(routes, DOCUMENT).paths or {})["/search"].get
        assert described is not None
        parameter = typing.cast(openapi.Parameter, (described.parameters or ())[0])
        assert (parameter.name, parameter.in_, parameter.required, parameter.schema) == (
            "q",
            openapi.ParameterLocation.QUERY,
            True,
            {"type": "string"},
        )

    def test_an_optional_query_parameter_is_not_required(self) -> None:
        async def search(request: Request, q: Query[str] = "") -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.get("/search")(search)
        described = (build_document(routes, DOCUMENT).paths or {})["/search"].get
        assert described is not None
        parameter = typing.cast(openapi.Parameter, (described.parameters or ())[0])
        assert parameter.required is False

    def test_a_query_parameter_may_rename_the_key(self) -> None:
        async def search(request: Request, source: typing.Annotated[str, QueryParam("utm-source")]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.get("/search")(search)
        described = (build_document(routes, DOCUMENT).paths or {})["/search"].get
        assert described is not None
        parameter = typing.cast(openapi.Parameter, (described.parameters or ())[0])
        assert parameter.name == "utm-source"

    def test_a_query_model_explodes_into_parameters(self) -> None:
        async def search(request: Request, filters: Query[Filters]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.get("/search")(search)
        described = (build_document(routes, DOCUMENT).paths or {})["/search"].get
        assert described is not None
        names = [typing.cast(openapi.Parameter, parameter).name for parameter in described.parameters or ()]
        assert names == ["page", "tags"]

    def test_a_json_body_is_a_request_body(self) -> None:
        async def create(request: Request, user: Body[User]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.post("/users")(create)
        document = build_document(routes, DOCUMENT)
        described = (document.paths or {})["/users"].post
        assert described is not None
        body = described.request_body
        assert isinstance(body, openapi.RequestBody)
        assert "$ref" in (body.content["application/json"].schema or {})
        assert document.components is not None
        assert "User" in (document.components.schemas or {})

    def test_a_typed_json_response_contributes_body_status_and_headers(self) -> None:
        async def show(request: Request) -> JSONResponse[User, typing.Literal[201], UserHeaders]:
            return JSONResponse({})  # pragma: no cover

        routes = Routes()
        routes.post("/users")(show)
        document = build_document(routes, DOCUMENT)
        operation = (document.paths or {})["/users"].post
        assert operation is not None
        response = typing.cast(openapi.Response, (operation.responses or {})["201"])

        assert response.content == {"application/json": openapi.MediaType(schema={"$ref": "#/components/schemas/User"})}
        assert response.headers == {
            "XRequestId": openapi.Header(schema={"type": "string"}, required=False),
        }

    def test_a_typed_json_response_can_describe_a_list(self) -> None:
        async def list_users(
            request: Request,
        ) -> JSONResponse[list[User], typing.Literal[200], typing.Mapping[str, str]]:
            return JSONResponse([])  # pragma: no cover

        routes = Routes()
        routes.get("/users")(list_users)
        document = build_document(routes, DOCUMENT)
        operation = (document.paths or {})["/users"].get
        assert operation is not None
        response = typing.cast(openapi.Response, (operation.responses or {})["200"])

        assert response.content == {
            "application/json": openapi.MediaType(
                schema={"type": "array", "items": {"$ref": "#/components/schemas/User"}}
            )
        }

    @pytest.mark.parametrize(
        ("annotation", "expected"),
        [
            (list[User], {"type": "array", "items": {"$ref": "#/components/schemas/User"}}),
            (typing.Sequence[User], {"type": "array", "items": {"$ref": "#/components/schemas/User"}}),
            (typing.Iterable[User], {"type": "array", "items": {"$ref": "#/components/schemas/User"}}),
            (collections.abc.Sequence[User], {"type": "array", "items": {"$ref": "#/components/schemas/User"}}),
            (collections.abc.Iterable[User], {"type": "array", "items": {"$ref": "#/components/schemas/User"}}),
            (
                set[User],
                {"type": "array", "items": {"$ref": "#/components/schemas/User"}, "uniqueItems": True},
            ),
            (
                collections.abc.Set[User],
                {"type": "array", "items": {"$ref": "#/components/schemas/User"}, "uniqueItems": True},
            ),
            (
                frozenset[User],
                {"type": "array", "items": {"$ref": "#/components/schemas/User"}, "uniqueItems": True},
            ),
            (
                dict[str, User],
                {"type": "object", "additionalProperties": {"$ref": "#/components/schemas/User"}},
            ),
            (
                typing.Mapping[str, User],
                {"type": "object", "additionalProperties": {"$ref": "#/components/schemas/User"}},
            ),
        ],
    )
    def test_schema_for_json_collections(self, annotation: typing.Any, expected: openapi.Schema) -> None:
        assert OpenAPIBuilder().schema_for(annotation) == expected

    @pytest.mark.parametrize(
        "annotation",
        [
            list,
            set,
            typing.Sequence,
            typing.Iterable,
            list[typing.Any],
            set[typing.Any],
            frozenset[typing.Any],
            dict[int, User],
            tuple[User, ...],
        ],
    )
    def test_schema_for_rejects_unsupported_json_collections(self, annotation: typing.Any) -> None:
        with pytest.raises(UnsupportedSchemaError):
            OpenAPIBuilder().schema_for(annotation)

    def test_authored_response_fields_override_generated_fields(self) -> None:
        async def show(request: Request) -> JSONResponse[User, typing.Literal[200], UserHeaders]:
            return JSONResponse({})  # pragma: no cover

        routes = Routes()
        routes.get("/users", responses={"200": openapi.Response(description="Users.")})(show)
        operation = (build_document(routes, DOCUMENT).paths or {})["/users"].get
        assert operation is not None
        response = typing.cast(openapi.Response, (operation.responses or {})["200"])

        assert response.description == "Users."
        assert response.content == {"application/json": openapi.MediaType(schema={"$ref": "#/components/schemas/User"})}

    def test_a_non_literal_response_status_is_rejected(self) -> None:
        async def show(request: Request) -> JSONResponse[User, int, typing.Mapping[str, str]]:
            return JSONResponse({})  # pragma: no cover

        routes = Routes()
        routes.get("/users")(show)
        with pytest.raises(ValueError, match="Literal"):
            build_document(routes, DOCUMENT)

    def test_a_response_annotation_is_rejected_when_it_has_too_few_types(self) -> None:
        annotation = types.GenericAlias(JSONResponse, (User, typing.Literal[200]))
        with pytest.raises(ValueError, match="body, status, and headers"):
            parse_response(annotation)

    def test_a_response_annotation_is_rejected_when_status_is_not_an_http_code(self) -> None:
        annotation = JSONResponse[User, typing.Literal[99], typing.Mapping[str, str]]
        with pytest.raises(ValueError, match="HTTP status codes"):
            parse_response(annotation)

    def test_schema_for_unwraps_annotated_models(self) -> None:
        assert OpenAPIBuilder().schema_for(typing.Annotated[User, "metadata"]) == {"$ref": "#/components/schemas/User"}

    def test_a_form_model_is_a_request_body(self) -> None:
        async def submit(request: Request, filters: Form[Filters]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.post("/search")(submit)
        described = (build_document(routes, DOCUMENT).paths or {})["/search"].post
        assert described is not None
        body = described.request_body
        assert isinstance(body, openapi.RequestBody)
        assert "application/x-www-form-urlencoded" in body.content

    def test_form_fields_and_a_form_model_share_one_request_body(self) -> None:
        async def update(request: Request, kek: Form[str], body: Form[User]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.put("/users")(update)
        described = (build_document(routes, DOCUMENT).paths or {})["/users"].put
        assert described is not None
        schema = described.request_body
        assert isinstance(schema, openapi.RequestBody)
        form = schema.content["application/x-www-form-urlencoded"].schema
        assert form is not None
        assert set(form["properties"]) == {"kek", "name"}
        assert form["required"] == ["kek", "name"]

    def test_the_same_model_on_two_routes_is_one_component(self) -> None:
        async def create(request: Request, user: Body[User]) -> Response:
            return Response()  # pragma: no cover

        async def replace(request: Request, user: Body[User]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.post("/users")(create)
        routes.put("/users")(replace)
        schemas = (build_document(routes, DOCUMENT).components or openapi.Components()).schemas or {}
        assert list(schemas) == ["User"]

    def test_two_models_with_the_same_name_are_qualified(self) -> None:
        class Admin:
            class User(pydantic.BaseModel):
                name: str

        async def create(request: Request, user: Body[Admin.User]) -> Response:
            return Response()  # pragma: no cover

        async def other(request: Request, user: Body[User]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.post("/local")(create)
        routes.post("/shared")(other)
        schemas = (build_document(routes, DOCUMENT).components or openapi.Components()).schemas or {}
        assert set(schemas) == {"User", "test_schema_builder.User"}

    def test_body_and_form_on_one_endpoint_are_refused(self) -> None:
        async def mixed(request: Request, user: Body[User], filters: Form[Filters]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.post("/mixed")(mixed)
        with pytest.raises(DuplicateOperationError, match="two request bodies"):
            build_document(routes, DOCUMENT)

    def test_a_custom_namer_names_the_component(self) -> None:
        async def create(request: Request, user: Body[User]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.post("/users")(create)
        schemas = (
            build_document(routes, DOCUMENT, namer=lambda type_, taken: f"X{type_.__name__}").components
            or openapi.Components()
        ).schemas or {}
        assert list(schemas) == ["XUser"]

    def test_a_namer_that_repeats_a_name_is_refused(self) -> None:
        async def create(request: Request, user: Body[User]) -> Response:
            return Response()  # pragma: no cover

        async def submit(request: Request, filters: Body[Filters]) -> Response:
            return Response()  # pragma: no cover

        routes = Routes()
        routes.post("/users")(create)
        routes.post("/filters")(submit)
        with pytest.raises(ValueError, match="already used"):
            build_document(routes, DOCUMENT, namer=lambda type_, taken: "Same")


class TestDefaultSchemaNamer:
    def test_prefers_the_class_name(self) -> None:
        assert default_schema_namer(User, set()) == "User"

    def test_qualifies_when_the_short_name_is_taken(self) -> None:
        assert default_schema_namer(User, {"User"}) == "test_schema_builder.User"

    def test_rejects_when_all_names_are_taken(self) -> None:
        module_name = User.__module__
        taken = {
            User.__name__,
            f"{module_name.rsplit('.', 1)[-1]}.{User.__name__}",
            f"{module_name}.{User.__qualname__}",
        }
        with pytest.raises(ValueError, match="unique schema name"):
            default_schema_namer(User, taken)


def test_rewrites_nested_schema_references() -> None:
    assert _rewrite_refs(
        {"nested": [{"$ref": "#/components/schemas/Old"}]},
        {"Old": "New"},
    ) == {"nested": [{"$ref": "#/components/schemas/New"}]}
    assert _rewrite_refs({"$ref": "#/components/schemas/Old"}, {"Old": "New"}) == {"$ref": "#/components/schemas/New"}
    assert _rewrite_refs({"$ref": "#/components/schemas/Other"}, {"Old": "New"}) == {
        "$ref": "#/components/schemas/Other"
    }


def test_splits_a_root_definition_from_library_schema() -> None:
    root, definitions = _split_library_schema({"$ref": "#/$defs/User", "$defs": {"User": {"type": "object"}}})
    assert root == {"type": "object"}
    assert definitions == {}
    assert _split_library_schema({"$ref": "#/$defs/User", "$defs": {"Other": {"type": "object"}}}) == (
        {"$ref": "#/$defs/User"},
        {"Other": {"type": "object"}},
    )


def test_reuses_a_registered_schema_name() -> None:
    builder = OpenAPIBuilder()
    assert builder.name_for(User) == "User"
    assert builder.name_for(User) == "User"


def test_registers_and_skips_colliding_nested_definitions() -> None:
    class First:
        pass

    class Second:
        pass

    schema = {"type": "object", "$defs": {"Nested": {"type": "object"}}}
    builder = OpenAPIBuilder()
    builder.register(First, schema)
    builder.schemas["Second.Nested"] = {"type": "string"}
    builder.register(Second, schema)
    assert builder.schemas["Nested"] == {"type": "object"}
    assert builder.schemas["Second.Nested"] == {"type": "string"}


def test_rejects_a_model_binder_for_a_non_type() -> None:
    class Binder:
        def supports(self, type_: typing.Any) -> bool:
            return True

        def schema(self, type_: typing.Any) -> openapi.Schema:
            raise NotImplementedError

    builder = OpenAPIBuilder((typing.cast(typing.Any, Binder()),))
    with pytest.raises(UnsupportedSchemaError):
        builder.schema_for(list[User])


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [(enum.Enum("StringEnum", {"one": "one"}), "string"), (enum.Enum("IntegerEnum", {"one": 1}), "integer")],
)
def test_schema_for_enums(annotation: type[enum.Enum], expected: str) -> None:
    assert OpenAPIBuilder().schema_for(annotation) == {"type": expected, "enum": [next(iter(annotation)).value]}


def test_properties_of_a_non_model_schema() -> None:
    assert OpenAPIBuilder().properties_of(dict[str, int]) == ({}, frozenset())


def test_merge_responses_keeps_non_response_authored_values() -> None:
    reference = openapi.Reference(ref="#/components/responses/Other")
    merged = merge_responses({"200": openapi.Response(description="Generated")}, {"200": reference})
    assert merged == {"200": reference}
