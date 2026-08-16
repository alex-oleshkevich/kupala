import typing

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.responses import PlainTextResponse
from starlette.routing import Host, Mount, Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.applications import Kupala
from kupala.middleware import (
    CallNext,
    Middleware,
    WebSocketCallNext,
)
from kupala.requests import Request
from kupala.responses import Response, response
from kupala.routing import (
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
        compiled_routes = nested_routes.compile(app.resolver, tuple(app.middleware))

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
        compiled_routes = routes.compile(app.resolver, tuple(app.middleware))

        assert any(isinstance(route, Route) for route in compiled_routes)
        assert any(isinstance(route, WebSocketRoute) for route in compiled_routes)

        app = Kupala("tests", routes=composed_routes)
        compiled_routes = composed_routes.compile(app.resolver, tuple(app.middleware))

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
