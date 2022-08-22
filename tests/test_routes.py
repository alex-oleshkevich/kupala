import os
import typing as t
from starlette.types import ASGIApp, Receive, Scope, Send
from unittest import mock

from kupala.http import route
from kupala.http.middleware import Middleware
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse, Response
from kupala.http.routing import Router, Routes
from kupala.http.websockets import WebSocket
from tests.conftest import TestClientFactory


@route("/")
async def view(request: Request) -> Response:
    return Response(request.url.path)


@route("/users", name="users")
async def users_view(request: Request) -> Response:
    return Response(request.url.path)


class SampleMiddleware:
    def __init__(self, app: ASGIApp, callback: t.Callable = None) -> None:
        self.app = app
        self.callback = callback

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.callback:
            self.callback()
        return await self.app(scope, receive, send)


def test_add(test_client_factory: TestClientFactory) -> None:
    client = test_client_factory(routes=[view])
    assert client.get("/").status_code == 200


def test_websocket(test_client_factory: TestClientFactory) -> None:
    async def view(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("websocket data")
        await websocket.close(1001)

    routes = Routes()
    routes.websocket("/ws", view)
    client = test_client_factory(routes=routes)

    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "websocket data"


def test_mount(test_client_factory: TestClientFactory) -> None:
    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    routes = Routes()
    routes.mount("/asgi", asgi)
    client = test_client_factory(routes=routes)

    response = client.get("/asgi")
    assert response.status_code == 200
    assert response.text == "ok"


def test_mount_calls_guards(test_client_factory: TestClientFactory) -> None:
    guard_called = mock.MagicMock()

    def guard(request: Request) -> None:
        guard_called()

    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    routes = Routes()
    routes.mount("/asgi", asgi, guards=[guard])
    client = test_client_factory(routes=routes)

    client.get("/asgi")
    guard_called.assert_called_once()


def test_static(test_client_factory: TestClientFactory, tmp_path: str) -> None:
    styles = os.path.join(str(tmp_path), "styles.css")
    with open(styles, "w") as f:
        f.write("body {}")

    routes = Routes()
    routes.static("/static", tmp_path)
    client = test_client_factory(routes=routes)

    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert response.text == "body {}"


def test_redirect(test_client_factory: TestClientFactory) -> None:
    routes = Routes()
    routes.redirect("/profile", "/login")
    client = test_client_factory(routes=routes)
    response = client.get("/profile/", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_host(test_client_factory: TestClientFactory) -> None:
    routes = Routes()
    with routes.host("api.example.com") as api:
        api.add(users_view)

    client = test_client_factory(routes=routes)
    response = client.get("/users/", headers={"host": "api.example.com"})
    assert response.status_code == 200
    assert response.text == "/users"


def test_host_with_initial_routes(test_client_factory: TestClientFactory) -> None:
    routes = Routes()
    routes.host("api.example.com", routes=[users_view])

    client = test_client_factory(routes=routes)
    response = client.get("/users/", headers={"host": "api.example.com"})
    assert response.status_code == 200


def test_host_url_generation() -> None:
    routes = Routes()
    with routes.host("api.example.com") as api:
        api.add(users_view)
    router = Router(routes=routes)
    assert router.url_path_for("users") == "/users"


def test_host_with_middleware(test_client_factory: TestClientFactory) -> None:
    call_stack: list[str] = []

    middleware = [
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("one")),
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("two")),
    ]
    routes = Routes()
    with routes.host("api.example.com", middleware=middleware) as api:
        api.add(users_view)

    client = test_client_factory(routes=routes)
    assert client.get("/users", headers={"host": "api.example.com"}).status_code == 200
    assert call_stack == ["one", "two"]  # check middleware call order


def test_host_calls_guards(test_client_factory: TestClientFactory) -> None:
    guard_called = mock.MagicMock()

    def guard(request: Request) -> None:
        guard_called()

    routes = Routes()
    with routes.host("api.example.com", guards=[guard]) as api:
        api.add(view)
    client = test_client_factory(routes=routes)
    client.get("/", headers={"host": "api.example.com"})
    guard_called.assert_called_once()


def test_group(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def index_view(request: Request) -> Response:
        return Response(request.url.path)

    @route("/create")
    def create_view(request: Request) -> Response:
        return Response(request.url.path)

    routes = Routes()
    with routes.group("/admin") as admin:
        admin.add(index_view)
        admin.add(create_view)

    client = test_client_factory(routes=routes)
    response = client.get("/admin")
    assert response.status_code == 200
    assert response.text == "/admin/"
    #
    # response = client.get("/admin/create")
    # assert response.status_code == 200
    # assert response.text == "/admin/create"


def test_group_with_initial_routes(test_client_factory: TestClientFactory) -> None:
    @route("/create")
    def admin_create_view() -> PlainTextResponse:
        return PlainTextResponse("")

    routes = Routes()
    routes.group("/admin", routes=[view, admin_create_view])

    client = test_client_factory(routes=routes)
    response = client.get("/admin/")
    assert response.status_code == 200

    response = client.get("/admin/create/")
    assert response.status_code == 200


def test_group_url_generation() -> None:
    @route("/users", name="admin_users")
    def admin_users_view() -> PlainTextResponse:
        return PlainTextResponse("")

    @route("/items", name="category_items")
    def category_items_view() -> PlainTextResponse:
        return PlainTextResponse("")

    routes = Routes()
    with routes.group("/admin") as admin:
        admin.add(admin_users_view)
        with admin.group("/category") as category:
            category.add(category_items_view)

    router = Router(routes=routes)
    assert router.url_path_for("admin_users") == "/admin/users"
    assert router.url_path_for("category_items") == "/admin/category/items"


def test_group_with_middleware(test_client_factory: TestClientFactory) -> None:
    call_stack: list[str] = []

    middleware = [
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("one")),
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("two")),
    ]
    routes = Routes()
    with routes.group("/admin", middleware=middleware) as api:
        api.add(users_view)

    client = test_client_factory(routes=routes)
    assert client.get("/admin/users").status_code == 200
    assert call_stack == ["one", "two"]  # check middleware call order


def test_group_calls_guards(test_client_factory: TestClientFactory) -> None:
    guard_called = mock.MagicMock()

    def guard(request: Request) -> None:
        guard_called()

    routes = Routes()
    with routes.group("/admin", guards=[guard]) as api:
        api.add(users_view)

    client = test_client_factory(routes=routes)
    client.get("/admin/users")
    guard_called.assert_called_once()


def test_group_url_generation_with_middleware() -> None:
    call_stack: list[str] = []
    middleware = [Middleware(SampleMiddleware, callback=lambda: call_stack.append("one"))]
    middleware2 = [Middleware(SampleMiddleware, callback=lambda: call_stack.append("two"))]

    @route("/items", name="category_items")
    def items_view(request: Request) -> Response:
        return PlainTextResponse("")

    routes = Routes()
    with routes.group("/admin", middleware=middleware) as admin:
        admin.add(users_view)

        with admin.group("/category", middleware=middleware2) as category:
            category.add(items_view)

    router = Router(routes=routes)
    assert router.url_path_for("users") == "/admin/users"
    assert router.url_path_for("category_items") == "/admin/category/items"


def test_sizeable() -> None:
    routes = Routes()
    routes.add(view)
    routes.add(view)
    assert len(routes) == 2


def test_iterable(routes: Routes) -> None:
    routes = Routes()
    routes.add(view)
    routes.add(view)
    assert len(list(routes)) == 2


def test_include_routes_instance(test_client_factory: TestClientFactory) -> None:
    @route("/included")
    def included_view(request: Request) -> Response:
        return PlainTextResponse("")

    routes = Routes()
    routes.include(Routes([included_view]))
    client = test_client_factory(routes=routes)
    assert client.get("/included").status_code == 200


def test_include_routes_list(test_client_factory: TestClientFactory) -> None:
    @route("/included")
    def included_view(request: Request) -> Response:
        return PlainTextResponse("")

    routes = Routes()
    routes.include([included_view])
    client = test_client_factory(routes=routes)
    assert client.get("/included").status_code == 200


def test_include_routes_string(test_client_factory: TestClientFactory) -> None:
    routes = Routes()
    routes.include("tests.assets.routes")
    client = test_client_factory(routes=routes)
    assert client.get("/callback-included").status_code == 200
