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
    walk,
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


class TestWalk:
    def test_joins_the_prefix_and_namespace_of_every_enclosing_group(self) -> None:
        routes = Routes(prefix="/api", namespace="api")
        group = routes.group("/v1", namespace="v1")
        group.get("/users", name="index")(view)

        assert [(path, name) for path, name, _ in walk(routes)] == [("/api/v1/users", "api.v1.index")]

    def test_names_a_route_after_its_endpoint_when_it_has_no_name(self) -> None:
        routes = Routes()
        routes.get("/users")(view)

        assert [name for _, name, _ in walk(routes)] == ["view"]

    def test_skips_a_route_kept_out_of_the_schema(self) -> None:
        routes = Routes()
        routes.get("/public")(view)
        routes.get("/private", include_in_schema=False)(view)

        assert [path for path, _, _ in walk(routes)] == ["/public"]

    def test_skips_what_it_cannot_describe(self) -> None:
        async def legacy(scope: Scope, receive: Receive, send: Send) -> None: ...  # pragma: no cover

        async def socket(websocket: WebSocket) -> None: ...  # pragma: no cover

        routes = Routes()
        routes.get("/users")(view)
        routes.websocket("/ws")(socket)
        routes.mount("/legacy", legacy)

        assert [path for path, _, _ in walk(routes)] == ["/users"]


class TestBuildDocument:
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

    def test_two_operations_cannot_share_an_id(self) -> None:
        routes = Routes()
        routes.get("/users", operation_id="same")(view)
        routes.get("/posts", operation_id="same")(view)

        with pytest.raises(DuplicateOperationError, match="'same' describes both"):
            build_document(routes, DOCUMENT)

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
