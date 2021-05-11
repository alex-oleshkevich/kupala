import os

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from kupala.application import App
from kupala.routing import Host
from kupala.routing import Route
from kupala.routing import Router
from kupala.routing import Routes


@pytest.fixture()
def app() -> App:
    return App()


def view(request: Request):
    return JSONResponse(
        {
            "method": request.method,
            "path_params": dict(request.path_params),
        }
    )


@pytest.fixture()
def test_client(app):
    return TestClient(app)


def test_get(test_client, app):
    app.routes.get("/", view)
    assert test_client.get("/").status_code == 200


def test_post(test_client, app):
    app.routes.post("/", view)
    assert test_client.post("/").status_code == 200


def test_get_or_post(test_client, app):
    app.routes.get_or_post("/", view)
    assert test_client.get("/").status_code == 200
    assert test_client.post("/").status_code == 200


def test_put(test_client, app):
    app.routes.put("/", view)
    assert test_client.put("/").status_code == 200


def test_patch(test_client, app):
    app.routes.patch("/", view)
    assert test_client.patch("/").status_code == 200


def test_delete(test_client, app):
    app.routes.delete("/", view)
    assert test_client.delete("/").status_code == 200


def test_options(test_client, app):
    app.routes.options("/", view)
    assert test_client.options("/").status_code == 200


def test_any(test_client, app):
    app.routes.any("/", view)
    assert test_client.get("/").status_code == 200
    assert test_client.post("/").status_code == 200


def test_add(test_client, app):
    app.routes.add("/", view, methods=["GET", "DELETE"])
    assert test_client.get("/").status_code == 200
    assert test_client.delete("/").status_code == 200


def test_redirect(test_client, app):
    app.routes.redirect("/profile", "/login")
    response = test_client.get("/profile/", allow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_websocket(test_client, app):
    async def view(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("websocket data")
        await websocket.close(1001)

    app.routes.websocket("/ws", view)

    with test_client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "websocket data"


def test_group(test_client, app):
    with app.routes.group("/admin") as admin:
        admin.get("/", view)
        admin.post("/create/", view, name="admin-create")

    response = test_client.get("/admin/")
    assert response.status_code == 200

    response = test_client.post("/admin/create/")
    assert response.status_code == 200


def mw_1(app, name, stack: list):
    async def wrapped(scope, receive, send):
        stack.append(name)
        await app(scope, receive, send)

    return wrapped


def test_group_with_middleware(test_client, app):
    call_stack = []
    with app.middleware.group("admin") as admin_mw:
        admin_mw.use(mw_1, name="mw1", stack=call_stack)
        admin_mw.use(mw_1, name="mw2", stack=call_stack)
        admin_mw.use(mw_1, name="mw3", stack=call_stack)

    with app.routes.group("/admin/", middleware=["admin"]) as admin:
        admin.get("/", view)
        admin.post("/create", view)

    response = test_client.get("/admin/")
    assert response.status_code == 200
    assert call_stack == ["mw1", "mw2", "mw3"]


def test_host(test_client, app):
    with app.routes.host("api.example.com") as api:
        api.get("/v1/users/", view, name="api-users")

    response = test_client.get(
        "/v1/users/",
        headers={
            "host": "api.example.com",
        },
    )
    assert response.status_code == 200


def test_host_with_middleware(test_client, app):
    call_stack = []
    with app.middleware.group("admin") as admin_mw:
        admin_mw.use(mw_1, name="mw1", stack=call_stack)

    with app.routes.host(
        "api.example.com",
        middleware=["admin"],
    ) as admin:
        admin.get("/v1/users/", view)

    response = test_client.get("/v1/users/", headers={"host": "api.example.com"})
    assert response.status_code == 200
    assert call_stack == ["mw1"]


def test_mount(test_client, app):
    async def asgi(scope, receive, send):
        await PlainTextResponse("ok")(scope, receive, send)

    app.routes.mount("/asgi", asgi)

    response = test_client.get("/asgi")
    assert response.status_code == 200
    assert response.text == "ok"


def test_static(test_client, app, tmp_path):
    styles = os.path.join(str(tmp_path), "styles.css")
    with open(styles, "w") as f:
        f.write("body {}")

    app.routes.static("/static", tmp_path)

    response = test_client.get("/static/styles.css")
    assert response.status_code == 200
    assert response.text == "body {}"


def test_host_route(test_client, app):
    host = Host("api.example.com")
    with host as routes:
        routes.get("/v1/users/", view, name="api")

    app = Router([host])
    assert app.url_path_for("api") == "/v1/users/"


def test_include():
    routes = Routes()
    routes.include("tests.fixtures.routes")
    assert len(routes) == 1


def test_get_route_by_index():
    routes = Routes()
    routes.get("/", view)
    assert isinstance(routes[0], Route)
