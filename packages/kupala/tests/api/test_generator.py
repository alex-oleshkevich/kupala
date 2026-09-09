import typing

import pytest
from starlette.convertors import Convertor
from starlette.types import Receive, Scope, Send

from kupala import openapi
from kupala.api.generator import (
    DuplicateOperationError,
    build_document,
    convertor_schema,
    documented_methods,
    path_parameters,
)
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import RouteDefinition, Routes
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
