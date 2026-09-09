import threading
import typing

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
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
from kupala.requests import Request
from kupala.responses import Response, response
from kupala.routing import (
    RouteConflictError,
    RouteDefinition,
    Routes,
)
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


class TestRouteDefinitions:
    def test_definition_metadata(self, routes: Routes) -> None:
        metadata_routes = next(child for child in routes._children if child.namespace == "admin")
        definition = metadata_routes.definitions[0]

        assert isinstance(definition, RouteDefinition)

        assert definition.path == "/users/"
        assert definition.name == "list_users"
        assert definition.methods == ("GET", "HEAD")

    def test_nested_groups_compile_prefix_and_namespace(self, nested_routes: Routes) -> None:
        app = Kupala("tests", routes=nested_routes)
        compiled_routes = nested_routes.compile(tuple(app.middleware))

        profile_route = next(
            route for route in compiled_routes if isinstance(route, Route) and route.name == "api.users.private.profile"
        )

        assert profile_route.path == "/api/users/private/profile"


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
