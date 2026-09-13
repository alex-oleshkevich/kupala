import threading
import typing

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Host, Mount, Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect

from kupala.applications import Kupala
from kupala.dependencies import Factory, Injected, UnsupportedParameterError, Value
from kupala.middleware import (
    CallNext,
    Middleware,
    WebSocketCallNext,
)
from kupala.params import Query
from kupala.requests import Request
from kupala.responses import Response, response
from kupala.routing import (
    RouteConflictError,
    RouteDefinition,
    Routes,
    split_docstring,
)
from kupala.schema import openapi
from kupala.security import Bearer
from kupala.websockets import WebSocket


class HostEventMiddleware:
    def __init__(self, app: ASGIApp, events: list[str]) -> None:
        self.app = app
        self.events = events

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.events.append("before")
        await self.app(scope, receive, send)
        self.events.append("after")


def stub_endpoint(request: Request) -> Response:
    raise AssertionError("route-shape tests never invoke the endpoint")  # pragma: no cover


class Connection:
    """Stands in for a request-scoped resource that must be opened exactly once, such as a session."""


class TaggedRequest(Request):
    """A request a middleware substitutes for the one the route was matched with."""


async def stub_websocket_endpoint(websocket: WebSocket) -> None:
    raise AssertionError("route-shape tests never invoke the endpoint")  # pragma: no cover


type AccessToken = typing.Annotated[str, Bearer(realm="test")]


async def require_access_token(
    request: Request,
    call_next: CallNext,
    /,
    _token: AccessToken,
) -> Response:
    return await call_next(request)


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def application_middleware(events: list[str]) -> list[Middleware]:
    async def app_middleware(request: Request, call_next: CallNext) -> Response:
        events.append("app-before")
        result = await call_next(request)
        events.append("app-after")
        return result

    return [app_middleware]


@pytest.fixture
def routes(events: list[str]) -> Routes:
    routes = Routes()

    @routes.get("/")
    async def get_endpoint(request: Request) -> Response:
        return response(request).text("ok")

    @routes.post("/post")
    async def post_endpoint(request: Request) -> Response:
        return response(request).text("post")

    @routes.get_or_post("/both")
    async def get_or_post_endpoint(request: Request) -> Response:
        return response(request).text(request.method)

    @routes.put("/put")
    async def put_endpoint(request: Request) -> Response:
        return response(request).text("put")

    @routes.patch("/patch")
    async def patch_endpoint(request: Request) -> Response:
        return response(request).text("patch")

    @routes.delete("/delete")
    async def delete_endpoint(request: Request) -> Response:
        return response(request).text("delete")

    @routes.head("/head")
    async def head_endpoint(request: Request) -> Response:
        return response(request).text("head")

    @routes.get("/resource")
    async def resource_endpoint(request: Request) -> Response:
        return response(request).text("resource")

    @routes.get("/sync")
    def sync_endpoint(request: Request) -> Response:
        return response(request).text("sync")

    async def route_middleware(request: Request, call_next: CallNext) -> Response:
        events.append("route-before")
        result = await call_next(request)
        events.append("route-after")
        return result

    @routes.get("/middleware", middleware=[route_middleware])
    async def middleware_endpoint(request: Request) -> Response:
        events.append("endpoint")
        return response(request).text("ok")

    async def websocket_middleware(
        websocket: WebSocket,
        call_next: WebSocketCallNext,
    ) -> None:
        events.append("websocket-before")
        await call_next(websocket)
        events.append("websocket-after")

    @routes.websocket("/socket", middleware=[websocket_middleware])
    async def websocket_endpoint(websocket: WebSocket) -> None:
        events.append("websocket-endpoint")
        await websocket.accept()
        await websocket.send_text("ready")

    metadata_routes = Routes(prefix="/api/", namespace="admin")

    @metadata_routes.get("/users/", name="list_users")
    async def metadata_endpoint(request: Request) -> Response:  # pragma: no cover
        return response(request).text("users")

    routes.include(metadata_routes)

    return routes


@pytest.fixture
def nested_routes(events: list[str]) -> Routes:
    routes = Routes()
    api_routes = routes.group("/api", namespace="api")
    users_routes = api_routes.group("/users", namespace="users")

    async def group_middleware(request: Request, call_next: CallNext) -> Response:  # pragma: no cover
        events.append("group-before")
        result = await call_next(request)
        events.append("group-after")
        return result

    private_routes = users_routes.group(
        "/private",
        namespace="private",
        middleware=[group_middleware],
    )

    @private_routes.get("/profile", name="profile")
    async def profile_endpoint(request: Request) -> Response:  # pragma: no cover
        events.append("profile")
        return response(request).text("profile")

    return routes


@pytest.fixture
def mounted_app() -> Starlette:
    async def mounted_endpoint(request: Request) -> PlainTextResponse:
        return PlainTextResponse("mounted")

    return Starlette(routes=[Route("/", mounted_endpoint)])


@pytest.fixture
def hosted_app() -> Starlette:
    async def hosted_endpoint(request: Request) -> PlainTextResponse:
        return PlainTextResponse("hosted")

    return Starlette(routes=[Route("/", hosted_endpoint)])


@pytest.fixture
def composed_routes(mounted_app: Starlette, hosted_app: Starlette) -> Routes:
    routes = Routes()
    routes.mount("/mounted", mounted_app, name="mounted")
    routes.host("api.example.com", hosted_app, name="api")
    return routes


@pytest.fixture
def test_client(routes: Routes, application_middleware: list[Middleware]) -> typing.Generator[TestClient]:
    app = Kupala(
        "tests",
        debug=True,
        routes=routes,
        middleware=application_middleware,
    )

    with TestClient(app) as client:
        yield client


class TestHTTPRoutes:
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("get", "/", "ok"),
            ("post", "/post", "post"),
            ("put", "/put", "put"),
            ("patch", "/patch", "patch"),
            ("delete", "/delete", "delete"),
            ("head", "/head", ""),
        ],
    )
    def test_http_methods(self, test_client: TestClient, method: str, path: str, body: str) -> None:
        http_response = test_client.request(method, path)

        assert http_response.status_code == 200
        assert http_response.text == body

    def test_get_or_post(self, test_client: TestClient) -> None:
        assert test_client.get("/both").text == "GET"
        assert test_client.post("/both").text == "POST"
        assert test_client.put("/both").status_code == 405

    def test_get_allows_head(self, test_client: TestClient) -> None:
        assert test_client.head("/resource").status_code == 200
        assert test_client.head("/resource").text == ""

    def test_sync_endpoint(self, test_client: TestClient) -> None:
        http_response = test_client.get("/sync")

        assert http_response.status_code == 200
        assert http_response.text == "sync"

    def test_callable_object_endpoint(self) -> None:
        class AsyncView:
            async def __call__(self, request: Request) -> Response:
                return response(request).text("async view")

        class SyncView:
            def __call__(self, request: Request) -> Response:
                return response(request).text("sync view")

        routes = Routes()
        # an instance carries its coroutine marker on __call__ and has no __name__ at all
        routes.get("/async")(AsyncView())
        routes.get("/sync")(SyncView())
        app = Kupala("tests", routes=routes)

        with TestClient(app) as client:
            assert client.get("/async").text == "async view"
            assert client.get("/sync").text == "sync view"

    def test_sync_endpoint_runs_off_the_event_loop(self) -> None:
        threads: dict[str, int] = {}
        routes = Routes()

        @routes.get("/async")
        async def async_endpoint(request: Request) -> Response:
            threads["async"] = threading.get_ident()
            return response(request).text("async")

        @routes.get("/sync")
        def sync_endpoint(request: Request) -> Response:
            threads["sync"] = threading.get_ident()
            return response(request).text("sync")

        app = Kupala("tests", routes=routes)
        with TestClient(app) as client:
            client.get("/async")
            client.get("/sync")

        assert threads["sync"] != threads["async"]

    def test_route_middleware_order(self, test_client: TestClient, events: list[str]) -> None:
        assert test_client.get("/middleware").text == "ok"
        assert events == [
            "app-before",
            "route-before",
            "endpoint",
            "route-after",
            "app-after",
        ]


class TestHTTPMiddlewareSecurityBoundaries:
    def test_router_responses_do_not_run_http_middleware(self) -> None:
        routes = Routes()

        @routes.get("/private/")
        async def private() -> Response:
            return Response("private")

        app = Kupala("tests", routes=routes, middleware=[require_access_token])

        with TestClient(app) as client:
            assert client.get("/private/").status_code == 401
            assert client.head("/private/").status_code == 401
            assert client.post("/private/").status_code == 405
            assert client.options("/private/").status_code == 405
            assert client.get("/missing").status_code == 404

            redirect = client.get("/private", follow_redirects=False)
            assert redirect.status_code == 307
            assert client.get(redirect.headers["location"]).status_code == 401

            authenticated = client.get("/private/", headers={"Authorization": "Bearer valid"})
            assert authenticated.text == "private"

    def test_cors_preflight_bypasses_http_middleware(self) -> None:
        routes = Routes()

        async def private() -> Response:
            return Response("private")

        routes.add("/private", private, methods=("GET", "HEAD", "OPTIONS"))
        app = Kupala(
            "tests",
            routes=routes,
            middleware=[require_access_token],
            asgi_middleware=[
                ASGIMiddlewareWrapper(
                    CORSMiddleware,
                    allow_origins=["https://client.example"],
                    allow_methods=["GET"],
                )
            ],
        )

        with TestClient(app) as client:
            preflight = client.options(
                "/private",
                headers={
                    "Origin": "https://client.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert preflight.status_code == 200

            assert client.options("/private").status_code == 401
            unauthorized = client.get("/private", headers={"Origin": "https://client.example"})
            assert unauthorized.status_code == 401
            assert unauthorized.headers["access-control-allow-origin"] == "https://client.example"

            authorized = client.get(
                "/private",
                headers={"Origin": "https://client.example", "Authorization": "Bearer valid"},
            )
            assert authorized.text == "private"
            assert authorized.headers["access-control-allow-origin"] == "https://client.example"

    def test_mounts_and_hosts_do_not_inherit_parent_http_middleware(self, composed_routes: Routes) -> None:
        app = Kupala("tests", routes=composed_routes, middleware=[require_access_token])

        with TestClient(app) as client:
            mounted_response = client.get("/mounted/")
            hosted_response = client.get("http://api.example.com/")

        assert mounted_response.status_code == 200
        assert hosted_response.status_code == 200


class TestRouteDefinitions:
    def test_definition_metadata(self, routes: Routes) -> None:
        metadata_routes = next(child for child in routes._children if child.namespace == "admin")
        definition = metadata_routes.definitions[0]

        assert isinstance(definition, RouteDefinition)

        assert definition.path == "/users/"
        assert definition.name == "list_users"
        assert definition.methods == ("GET", "HEAD")

    def test_inspects_its_endpoint_on_demand(self) -> None:
        routes = Routes()

        @routes.get("/search")
        async def search(request: Request, q: Query[str], page: Query[int] = 1) -> Response:
            return Response("")  # pragma: no cover

        definition = routes.definitions[0]
        assert isinstance(definition, RouteDefinition)

        assert definition.call.is_async is True
        assert definition.call.return_type is Response
        assert [param.name for param in definition.call.parameters] == ["request", "q", "page"]
        assert [type(binding).__name__ for param in definition.call.parameters for binding in param.metadata] == [
            "QueryParam",
            "QueryParam",
        ]
        # inspecting once is the point of caching it on the definition
        assert definition.call is definition.call

    def test_nested_groups_compile_prefix_and_namespace(self, nested_routes: Routes) -> None:
        app = Kupala("tests", routes=nested_routes)
        compiled_routes = nested_routes.compile(tuple(app.middleware))

        profile_route = next(
            route for route in compiled_routes if isinstance(route, Route) and route.name == "api.users.private.profile"
        )

        assert profile_route.path == "/api/users/private/profile"


class TestDescribe:
    def test_resolves_the_path_and_name_of_every_enclosing_group(self) -> None:
        routes = Routes(prefix="/api", namespace="api")
        group = routes.group("/v1", namespace="v1")

        @group.get("/users", name="index")
        async def index(request: Request) -> Response:
            return Response("[]")  # pragma: no cover

        assert [(info.path, info.name) for info in routes.describe()] == [("/api/v1/users", "api.v1.index")]

    def test_names_a_route_after_its_endpoint_when_it_has_none(self) -> None:
        routes = Routes()

        @routes.get("/users")
        async def list_users(request: Request) -> Response:
            return Response("[]")  # pragma: no cover

        assert [info.name for info in routes.describe()] == ["list_users"]

    def test_describes_a_route_kept_out_of_the_schema(self) -> None:
        # `describe` is the route tree, not the document: what a route opts out of is the caller's filter
        routes = Routes()

        @routes.get("/private", include_in_schema=False)
        async def private(request: Request) -> Response:
            return Response("")  # pragma: no cover

        assert [(info.path, info.definition.openapi) for info in routes.describe()] == [("/private", None)]

    def test_omits_what_has_no_http_shape(self) -> None:
        async def legacy(scope: Scope, receive: Receive, send: Send) -> None: ...  # pragma: no cover

        routes = Routes()

        @routes.get("/users")
        async def list_users(request: Request) -> Response:
            return Response("[]")  # pragma: no cover

        @routes.websocket("/ws")
        async def socket(websocket: WebSocket) -> None: ...  # pragma: no cover

        routes.mount("/legacy", legacy)
        routes.host("cdn.example.com", legacy)

        assert [info.path for info in routes.describe()] == ["/users"]

    def test_points_at_the_definition_it_resolved(self) -> None:
        routes = Routes()

        @routes.get_or_post("/search")
        async def search(request: Request) -> Response:
            return Response("")  # pragma: no cover

        info = next(iter(routes.describe()))

        assert info.definition is routes.definitions[0]
        assert info.definition.methods == ("GET", "HEAD", "POST")

    def test_one_definition_under_two_parents_resolves_twice(self) -> None:
        # a group may be included in several places, which is why a resolved path cannot live on the
        # definition: there is one of those and two right answers
        async def first_middleware(request: Request, call_next: CallNext) -> Response:
            return await call_next(request)  # pragma: no cover

        async def second_middleware(request: Request, call_next: CallNext) -> Response:
            return await call_next(request)  # pragma: no cover

        async def route_middleware(request: Request, call_next: CallNext) -> Response:
            return await call_next(request)  # pragma: no cover

        shared = Routes()

        @shared.get("/health", middleware=[route_middleware])
        async def health(request: Request) -> Response:
            return Response("ok")  # pragma: no cover

        root = Routes(
            children=[
                Routes(prefix="/a", namespace="a", middleware=[first_middleware], children=[shared]),
                Routes(prefix="/b", namespace="b", middleware=[second_middleware], children=[shared]),
            ]
        )

        described = list(root.describe())

        assert [(info.path, info.name) for info in described] == [("/a/health", "a.health"), ("/b/health", "b.health")]
        assert described[0].definition is described[1].definition
        assert described[0].middleware == (first_middleware, route_middleware)
        assert described[1].middleware == (second_middleware, route_middleware)

    def test_agrees_with_the_paths_and_names_compile_serves(self) -> None:
        # both resolve through `resolve_route`, and a document that disagreed with the router would
        # describe endpoints nobody can reach
        root = Routes(prefix="/root", namespace="root")

        @root.get("/first")
        async def first(request: Request) -> Response:
            return Response("")  # pragma: no cover

        inner = root.group("/inner", namespace="inner")

        @inner.get_or_post("/deep", name="deep")
        async def deep(request: Request) -> Response:
            return Response("")  # pragma: no cover

        @inner.delete("/deep")
        async def drop(request: Request) -> Response:
            return Response("")  # pragma: no cover

        described = sorted((info.path, info.name) for info in root.describe())
        compiled = sorted((route.path, route.name) for route in root.compile(()) if isinstance(route, Route))

        assert described == compiled
        assert described == [
            ("/root/first", "root.first"),
            ("/root/inner/deep", "root.inner.deep"),
            ("/root/inner/deep", "root.inner.drop"),
        ]

    def test_needs_no_compiled_application(self) -> None:
        # the manifest is import-time data, so a tool may read it before anything is built
        routes = Routes(prefix="/api")

        @routes.get("/users")
        async def list_users(request: Request) -> Response:
            return Response("[]")  # pragma: no cover

        assert [info.path for info in routes.describe()] == ["/api/users"]
        assert len(list(routes.describe())) == 1


class TestSplitDocstring:
    def test_reads_nothing_from_an_undocumented_endpoint(self) -> None:
        assert split_docstring(None) == (None, None)

    def test_a_single_paragraph_is_all_summary(self) -> None:
        assert split_docstring("List every user.") == ("List every user.", None)

    def test_the_first_paragraph_is_the_summary_and_the_rest_the_description(self) -> None:
        summary, description = split_docstring("""
            List every user,
            newest first.

            Paged at 100 per request.
            """)

        # a summary is one line in the specification, so a wrapped one is joined back up
        assert summary == "List every user, newest first."
        assert description == "Paged at 100 per request."


class TestOperationMetadata:
    def test_describes_an_endpoint_from_its_docstring(self) -> None:
        routes = Routes()

        @routes.get("/users")
        async def list_users(request: Request) -> Response:
            """List every user.

            Ordered by signup date.
            """
            return Response()  # pragma: no cover - the metadata is what this test reads

        definition = routes.definitions[0]
        assert isinstance(definition, RouteDefinition)
        assert definition.openapi is not None
        assert definition.openapi.summary == "List every user."
        assert definition.openapi.description == "Ordered by signup date."

    def test_options_win_over_the_docstring(self) -> None:
        routes = Routes()
        endpoint = routes.post(
            "/users",
            summary="Create a user",
            description="Long form.",
            operation_id="createUser",
            deprecated=True,
            tags=["users"],
        )

        endpoint(stub_endpoint)

        definition = routes.definitions[0]
        assert isinstance(definition, RouteDefinition)
        assert definition.openapi == openapi.Operation(
            tags=("users",),
            summary="Create a user",
            description="Long form.",
            operation_id="createUser",
            deprecated=True,
        )

    def test_an_undeclared_flag_stays_absent_rather_than_false(self) -> None:
        routes = Routes()
        routes.get("/users")(stub_endpoint)

        definition = routes.definitions[0]
        assert isinstance(definition, RouteDefinition)
        assert definition.openapi is not None
        assert definition.openapi.deprecated is None
        assert definition.openapi.tags is None

    def test_a_route_excluded_from_the_schema_carries_no_description(self) -> None:
        routes = Routes()
        routes.get("/openapi.json", include_in_schema=False)(stub_endpoint)

        definition = routes.definitions[0]
        assert isinstance(definition, RouteDefinition)
        assert definition.openapi is None

    def test_keeps_every_field_the_author_declared(self) -> None:
        # an option is any field of an operation, so one spelled correctly but not derived here was
        # accepted at the decorator and then dropped, which is the failure naming them all prevents
        routes = Routes()
        endpoint = routes.post(
            "/users",
            responses={"404": openapi.Response(description="No such user.")},
            request_body=openapi.RequestBody(content={"application/json": openapi.MediaType()}),
            parameters=[openapi.Parameter(name="trace", in_=openapi.ParameterLocation.HEADER)],
            security=[{"bearer": ("write",)}],
            external_docs=openapi.ExternalDocumentation(url="https://example.com/docs"),
            servers=[openapi.Server(url="https://api.example.com")],
            extensions={"x-internal": True},
        )

        endpoint(stub_endpoint)

        definition = routes.definitions[0]
        assert isinstance(definition, RouteDefinition)
        assert definition.openapi is not None
        assert definition.openapi.responses == {"404": openapi.Response(description="No such user.")}
        assert definition.openapi.request_body == openapi.RequestBody(content={"application/json": openapi.MediaType()})
        assert definition.openapi.parameters == [openapi.Parameter(name="trace", in_=openapi.ParameterLocation.HEADER)]
        assert definition.openapi.security == [{"bearer": ("write",)}]
        assert definition.openapi.external_docs == openapi.ExternalDocumentation(url="https://example.com/docs")
        assert definition.openapi.servers == [openapi.Server(url="https://api.example.com")]
        assert definition.openapi.extensions == {"x-internal": True}

    def test_derives_over_an_authored_field_without_disturbing_the_rest(self) -> None:
        routes = Routes(tags=["v1"])

        @routes.get("/users", responses={"200": openapi.Response(description="Users.")})
        async def list_users(request: Request) -> Response:
            """List users."""
            return Response()  # pragma: no cover - the metadata is what this test reads

        definition = routes.definitions[0]
        assert isinstance(definition, RouteDefinition)
        assert definition.openapi is not None
        assert definition.openapi.summary == "List users."
        assert definition.openapi.tags == ("v1",)
        assert definition.openapi.responses == {"200": openapi.Response(description="Users.")}

    def test_reports_a_misspelled_option_instead_of_dropping_it(self) -> None:
        routes = Routes()

        # the options dataclass is built by the decorator, so an option that does not exist is
        # rejected at the line that wrote it rather than silently losing its value
        with pytest.raises(TypeError, match="unexpected keyword argument 'tgs'"):
            routes.get("/users", tgs=["users"])

    def test_group_tags_accumulate_down_the_tree(self) -> None:
        routes = Routes(tags=["v1"])
        users = routes.group("/users", tags=["users"])
        users.get("/{id}", tags=["detail"])(stub_endpoint)

        definition = users.definitions[0]
        assert isinstance(definition, RouteDefinition)
        assert definition.openapi is not None
        assert definition.openapi.tags == ("v1", "users", "detail")


class TestWebSocketRoutes:
    def test_websocket_endpoint_and_middleware(self, test_client: TestClient, events: list[str]) -> None:
        with test_client.websocket_connect("/socket") as websocket:
            assert websocket.receive_text() == "ready"

        assert events == [
            "websocket-before",
            "websocket-endpoint",
            "websocket-after",
        ]

    def test_websocket_endpoint_resolves_dependencies(self) -> None:
        routes = Routes()

        @routes.websocket("/socket")
        async def websocket_endpoint(
            websocket: WebSocket,
            application: Injected[Kupala],
            greeting: typing.Annotated[str, Value("hello")],
        ) -> None:
            await websocket.accept()
            await websocket.send_text(f"{greeting} {application.name}")

        app = Kupala("di-app", routes=routes)

        with TestClient(app) as client, client.websocket_connect("/socket") as websocket:
            assert websocket.receive_text() == "hello di-app"

    def test_application_and_group_websocket_middleware_order(self) -> None:
        events: list[str] = []

        async def http_middleware(request: Request, call_next: CallNext) -> Response:
            raise AssertionError("HTTP middleware must not run for WebSocket routes")

        async def application_websocket_middleware(
            websocket: WebSocket,
            call_next: WebSocketCallNext,
        ) -> None:
            events.append("application-before")
            await call_next(websocket)
            events.append("application-after")

        async def group_websocket_middleware(
            websocket: WebSocket,
            call_next: WebSocketCallNext,
        ) -> None:
            events.append("group-before")
            await call_next(websocket)
            events.append("group-after")

        async def route_websocket_middleware(
            websocket: WebSocket,
            call_next: WebSocketCallNext,
        ) -> None:
            events.append("route-before")
            await call_next(websocket)
            events.append("route-after")

        routes = Routes().group(
            "/scope",
            websocket_middleware=[group_websocket_middleware],
        )

        @routes.websocket("/socket", middleware=[route_websocket_middleware])
        async def websocket_endpoint(websocket: WebSocket) -> None:
            events.append("endpoint")
            await websocket.accept()
            await websocket.send_text("ready")

        app = Kupala(
            "tests",
            routes=routes,
            middleware=[http_middleware],
            websocket_middleware=[application_websocket_middleware],
        )

        with TestClient(app) as client, client.websocket_connect("/scope/socket") as websocket:
            assert websocket.receive_text() == "ready"

        assert events == [
            "application-before",
            "group-before",
            "route-before",
            "endpoint",
            "route-after",
            "group-after",
            "application-after",
        ]

    def test_websocket_middleware_can_short_circuit(self) -> None:
        events: list[str] = []

        async def blocking_middleware(
            websocket: WebSocket,
            call_next: WebSocketCallNext,
        ) -> None:
            events.append("blocked")
            await websocket.close(code=4403)

        routes = Routes()
        endpoint = stub_websocket_endpoint
        routes.websocket("/blocked", name="blocked", middleware=[blocking_middleware])(endpoint)

        app = Kupala("tests", routes=routes)

        with TestClient(app) as client:
            websocket = client.websocket_connect("/blocked")
            with pytest.raises(WebSocketDisconnect) as error:
                websocket.__enter__()

        assert error.value.code == 4403
        assert events == ["blocked"]


class TestMiddlewareDependencies:
    """Middleware is invoked through the injector, so it declares what it needs like an endpoint."""

    def test_injects_dependencies_into_http_middleware(self) -> None:
        seen: list[str] = []

        async def middleware(
            request: Request, call_next: CallNext, /, greeting: typing.Annotated[str, Value("hello")]
        ) -> Response:
            seen.append(greeting)
            return await call_next(request)

        routes = Routes()

        @routes.get("/", middleware=[middleware])
        async def index() -> Response:
            return Response("ok")

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").text == "ok"

        assert seen == ["hello"]

    def test_middleware_and_endpoint_share_one_dependency(self) -> None:
        opened: list[Connection] = []
        seen: list[Connection] = []

        def open_connection() -> Connection:
            connection = Connection()
            opened.append(connection)
            return connection

        type Session = typing.Annotated[Connection, Factory(open_connection)]

        async def middleware(request: Request, call_next: CallNext, /, session: Session) -> Response:
            seen.append(session)
            return await call_next(request)

        routes = Routes()

        @routes.get("/", middleware=[middleware])
        async def index(session: Session) -> Response:
            seen.append(session)
            return Response("ok")

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").text == "ok"

        # the reason middleware needs the injector: one transaction, not two
        assert len(opened) == 1
        assert seen[0] is seen[1]

    def test_a_substituted_request_reaches_everything_below(self) -> None:
        seen: list[type[Request]] = []

        async def outer(request: Request, call_next: CallNext) -> Response:
            seen.append(type(request))
            return await call_next(TaggedRequest(request.scope, request.receive))

        async def inner(request: Request, call_next: CallNext) -> Response:
            seen.append(type(request))
            return await call_next(request)

        routes = Routes()

        @routes.get("/", middleware=[outer, inner])
        async def index(request: Request) -> Response:
            seen.append(type(request))
            return Response("ok")

        with TestClient(Kupala("tests", routes=routes)) as client:
            assert client.get("/").text == "ok"

        assert seen == [Request, TaggedRequest, TaggedRequest]

    def test_middleware_may_answer_without_continuing(self) -> None:
        async def guard(
            request: Request, call_next: CallNext, /, greeting: typing.Annotated[str, Value("denied")]
        ) -> Response:
            return Response(greeting, status_code=403)

        routes = Routes()

        @routes.get("/", middleware=[guard])
        async def index() -> Response:
            raise AssertionError("the endpoint must not run")  # pragma: no cover

        with TestClient(Kupala("tests", routes=routes)) as client:
            reply = client.get("/")

        assert reply.status_code == 403
        assert reply.text == "denied"

    def test_injects_dependencies_into_websocket_middleware(self) -> None:
        seen: list[str] = []

        async def middleware(
            websocket: WebSocket, call_next: WebSocketCallNext, /, greeting: typing.Annotated[str, Value("hello")]
        ) -> None:
            seen.append(greeting)
            await call_next(websocket)

        routes = Routes()

        @routes.websocket("/socket", middleware=[middleware])
        async def socket(websocket: WebSocket) -> None:
            await websocket.accept()
            await websocket.close()

        with TestClient(Kupala("tests", routes=routes)) as client, client.websocket_connect("/socket"):
            pass

        assert seen == ["hello"]

    def test_websocket_middleware_and_endpoint_share_one_dependency(self) -> None:
        opened: list[Connection] = []

        def open_connection() -> Connection:
            connection = Connection()
            opened.append(connection)
            return connection

        type Session = typing.Annotated[Connection, Factory(open_connection)]

        async def middleware(websocket: WebSocket, call_next: WebSocketCallNext, /, session: Session) -> None:
            await call_next(websocket)

        routes = Routes()

        @routes.websocket("/socket", middleware=[middleware])
        async def socket(websocket: WebSocket, session: Session) -> None:
            await websocket.accept()
            await websocket.close()

        with TestClient(Kupala("tests", routes=routes)) as client, client.websocket_connect("/socket"):
            pass

        assert len(opened) == 1


class TestMiddlewareSignature:
    """`Middleware` fixes the first two arguments, and a signature that cannot take them is rejected."""

    def test_rejects_a_middleware_that_cannot_take_the_fixed_arguments(self) -> None:
        async def middleware(request: Request) -> Response:
            return Response("ok")  # pragma: no cover

        routes = Routes()

        @routes.get("/", middleware=[typing.cast(Middleware, middleware)])
        async def index() -> Response:
            return Response("ok")  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            Kupala("tests", routes=routes)

        assert "must accept the request and the continuation" in str(info.value)

    def test_rejects_a_positional_only_dependency(self) -> None:
        async def middleware(
            request: Request, call_next: CallNext, greeting: typing.Annotated[str, Value("hi")], /
        ) -> Response:
            return await call_next(request)  # pragma: no cover

        routes = Routes()

        @routes.get("/", middleware=[typing.cast(Middleware, middleware)])
        async def index() -> Response:
            return Response("ok")  # pragma: no cover

        with pytest.raises(UnsupportedParameterError) as info:
            Kupala("tests", routes=routes)

        assert "'greeting'" in str(info.value)
        assert "passes dependencies by keyword" in str(info.value)


class TestMountedRoutes:
    def test_mount(self, composed_routes: Routes) -> None:
        app = Kupala("tests", routes=composed_routes)

        with TestClient(app) as client:
            http_response = client.get("/mounted/")

        assert http_response.status_code == 200
        assert http_response.text == "mounted"


class TestHostRoutes:
    def test_host(self, composed_routes: Routes) -> None:
        app = Kupala("tests", routes=composed_routes)

        with TestClient(app) as client:
            http_response = client.get("http://api.example.com/")

        assert http_response.status_code == 200
        assert http_response.text == "hosted"

    def test_host_middleware_runs_after_host_match(self) -> None:
        events: list[str] = []

        async def hosted_endpoint(request: Request) -> PlainTextResponse:
            events.append("endpoint")
            return PlainTextResponse("hosted")

        routes = Routes()
        routes.host(
            "api.example.com",
            Starlette(routes=[Route("/", hosted_endpoint)]),
            asgi_middleware=[ASGIMiddlewareWrapper(HostEventMiddleware, events=events)],
        )
        app = Kupala("tests", routes=routes)

        with TestClient(app) as client:
            http_response = client.get("http://api.example.com/")

            assert http_response.status_code == 200
            assert http_response.text == "hosted"
            assert events == ["before", "endpoint", "after"]

            events.clear()
            http_response = client.get("http://other.example.com/")

        assert http_response.status_code == 404
        assert events == []


class TestCompileRoutes:
    def test_compiles_all_definition_types(self, routes: Routes, composed_routes: Routes) -> None:
        app = Kupala("tests", routes=routes)
        compiled_routes = routes.compile(tuple(app.middleware))

        assert any(isinstance(route, Route) for route in compiled_routes)
        assert any(isinstance(route, WebSocketRoute) for route in compiled_routes)

        app = Kupala("tests", routes=composed_routes)
        compiled_routes = composed_routes.compile(tuple(app.middleware))

        assert any(isinstance(route, Mount) for route in compiled_routes)
        assert any(isinstance(route, Host) for route in compiled_routes)

    def test_route_definitions_remain_included_as_children(self) -> None:
        routes = Routes()
        child = Routes()

        @child.get("/included")
        async def included_endpoint(request: Request) -> Response:  # pragma: no cover
            return response(request).text("included")

        routes.include(child)

        assert len(routes.definitions) == 0
        assert len(routes._children) == 1
        assert len(routes._children[0].definitions) == 1

    def test_routes_collection_protocol(self) -> None:
        routes = Routes()

        @routes.get("/collection")
        async def collection_endpoint(request: Request) -> Response:  # pragma: no cover
            return response(request).text("collection")

        assert len(routes) == 1
        assert str(routes) == "Routes(1 definitions)"
        assert tuple(routes) == tuple(routes.definitions)

    def test_rejects_duplicate_http_routes(self) -> None:
        routes = Routes()
        endpoint = stub_endpoint
        routes.get("/users", name="first")(endpoint)
        routes.get("/users", name="second")(endpoint)

        with pytest.raises(RouteConflictError, match="Duplicate HTTP route GET '/users'"):
            Kupala("tests", routes=routes)

    def test_rejects_duplicate_nested_http_routes(self) -> None:
        routes = Routes()
        first = routes.group("/api")
        second = routes.group("/api")
        endpoint = stub_endpoint
        first.get("/users", name="first")(endpoint)
        second.get("/users", name="second")(endpoint)

        with pytest.raises(RouteConflictError, match="Duplicate HTTP route GET '/api/users'"):
            Kupala("tests", routes=routes)

    def test_rejects_duplicate_route_names(self) -> None:
        routes = Routes()
        endpoint = stub_endpoint
        routes.get("/users", name="shared")(endpoint)
        routes.get("/accounts", name="shared")(endpoint)

        with pytest.raises(RouteConflictError, match="Duplicate route name 'shared'"):
            Kupala("tests", routes=routes)

    def test_allows_same_path_for_different_http_methods(self) -> None:
        routes = Routes()
        endpoint = stub_endpoint
        routes.get("/users", name="get_users")(endpoint)
        routes.post("/users", name="create_user")(endpoint)

        app = Kupala("tests", routes=routes)

        assert len(routes.compile(tuple(app.middleware))) == 2

    def test_preserves_static_before_parameter_route_order(self) -> None:
        routes = Routes()

        @routes.get("/users/me")
        async def current_user(request: Request) -> Response:
            return response(request).text("me")

        routes.get("/users/{user_id}", name="user_detail")(stub_endpoint)

        app = Kupala("tests", routes=routes)

        with TestClient(app) as client:
            http_response = client.get("/users/me")

        assert http_response.text == "me"
