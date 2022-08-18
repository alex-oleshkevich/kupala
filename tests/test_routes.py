import os
import typing as t
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http.middleware import Middleware
from kupala.http.requests import Request
from kupala.http.responses import PlainTextResponse, Response
from kupala.http.routing import Route, Router, Routes
from kupala.http.websockets import WebSocket
from tests.conftest import TestClientFactory


async def view(request: Request) -> Response:
    return Response(request.url.path)


class SampleMiddleware:
    def __init__(self, app: ASGIApp, callback: t.Callable = None) -> None:
        self.app = app
        self.callback = callback

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.callback:
            self.callback()
        return await self.app(scope, receive, send)


def test_add(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes.add("/", view)
    client = test_client_factory(routes=routes)
    assert client.get("/").status_code == 200


def test_websocket(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def view(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("websocket data")
        await websocket.close(1001)

    routes.websocket("/ws", view)
    client = test_client_factory(routes=routes)

    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "websocket data"


def test_mount(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    routes.mount("/asgi", asgi)
    client = test_client_factory(routes=routes)

    response = client.get("/asgi")
    assert response.status_code == 200
    assert response.text == "ok"


def test_static(test_client_factory: TestClientFactory, routes: Routes, tmp_path: str) -> None:
    styles = os.path.join(str(tmp_path), "styles.css")
    with open(styles, "w") as f:
        f.write("body {}")

    routes.static("/static", tmp_path)
    client = test_client_factory(routes=routes)

    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert response.text == "body {}"


def test_redirect(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes.redirect("/profile", "/login")
    client = test_client_factory(routes=routes)
    response = client.get("/profile/", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_host(test_client_factory: TestClientFactory, routes: Routes) -> None:
    with routes.host("api.example.com") as api:
        api.add("/users", view, name="users")

    client = test_client_factory(routes=routes)
    response = client.get("/users/", headers={"host": "api.example.com"})
    assert response.status_code == 200
    assert response.text == "/users"


def test_host_with_initial_routes(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes.host("api.example.com", routes=[Route("/users", view)])

    client = test_client_factory(routes=routes)
    response = client.get("/users/", headers={"host": "api.example.com"})
    assert response.status_code == 200


def test_host_url_generation() -> None:
    routes = Routes()
    with routes.host("api.example.com") as api:
        api.add("/users", view, name="users")
    router = Router(routes=routes)
    assert router.url_path_for("users") == "/users"


def test_host_with_middleware(test_client_factory: TestClientFactory, routes: Routes) -> None:
    call_stack: list[str] = []

    middleware = [
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("one")),
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("two")),
    ]
    with routes.host("api.example.com", middleware=middleware) as api:
        api.add("/users", view, name="users")

    client = test_client_factory(routes=routes)
    assert client.get("/users", headers={"host": "api.example.com"}).status_code == 200
    assert call_stack == ["one", "two"]  # check middleware call order


def test_group(test_client_factory: TestClientFactory, routes: Routes) -> None:
    with routes.group("/admin") as admin:
        admin.add("/", view)
        admin.add("/create", view, name="admin-create", methods=["post"])

    client = test_client_factory(routes=routes)
    response = client.get("/admin")
    assert response.status_code == 200
    assert response.text == "/admin/"

    response = client.post("/admin/create")
    assert response.status_code == 200
    assert response.text == "/admin/create"


def test_group_with_initial_routes(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes.group(
        "/admin",
        routes=[
            Route("/", view),
            Route("/create/", view, name="admin-create", methods=["POST"]),
        ],
    )

    client = test_client_factory(routes=routes)
    response = client.get("/admin/")
    assert response.status_code == 200

    response = client.post("/admin/create/")
    assert response.status_code == 200


def test_group_url_generation() -> None:
    routes = Routes()
    with routes.group("/admin") as admin:
        admin.add("/users", view, name="admin_users")
        with admin.group("/category") as category:
            category.add("/items", view, name="category_items")

    router = Router(routes=routes)
    assert router.url_path_for("admin_users") == "/admin/users"
    assert router.url_path_for("category_items") == "/admin/category/items"


def test_group_with_middleware(test_client_factory: TestClientFactory, routes: Routes) -> None:
    call_stack: list[str] = []

    middleware = [
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("one")),
        Middleware(SampleMiddleware, callback=lambda: call_stack.append("two")),
    ]
    with routes.group("/admin", middleware=middleware) as api:
        api.add("/users", view, name="users")

    client = test_client_factory(routes=routes)
    assert client.get("/admin/users").status_code == 200
    assert call_stack == ["one", "two"]  # check middleware call order


def test_group_url_generation_with_middleware() -> None:
    call_stack: list[str] = []
    middleware = [Middleware(SampleMiddleware, callback=lambda: call_stack.append("one"))]
    middleware2 = [Middleware(SampleMiddleware, callback=lambda: call_stack.append("two"))]

    routes = Routes()
    with routes.group("/admin", middleware=middleware) as admin:
        admin.add("/users", view, name="admin_users")
        with admin.group("/category", middleware=middleware2) as category:
            category.add("/items", view, name="category_items")

    router = Router(routes=routes)
    assert router.url_path_for("admin_users") == "/admin/users"
    assert router.url_path_for("category_items") == "/admin/category/items"


def test_sizeable(routes: Routes) -> None:
    routes.add("/", view)
    routes.add("/two", view)
    assert len(routes) == 2


def test_iterable(routes: Routes) -> None:
    routes.add("/", view)
    routes.add("/two", view)
    assert len(list(routes)) == 2


def test_include_routes_instance(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes = Routes()
    routes.add("/included", view)

    routes.include(routes)
    client = test_client_factory(routes=routes)
    assert client.get("/included").status_code == 200


def test_include_routes_list(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes_to_include = [Route("/included", view)]

    routes.include(routes_to_include)
    client = test_client_factory(routes=routes)
    assert client.get("/included").status_code == 200


def test_include_routes_string(test_client_factory: TestClientFactory, routes: Routes) -> None:
    routes.include("tests.assets.routes")
    client = test_client_factory(routes=routes)
    assert client.get("/callback-included").status_code == 200
