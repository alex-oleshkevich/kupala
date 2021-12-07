import os
import pytest
import typing as t
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.application import Kupala
from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.responses import PlainTextResponse, Response
from kupala.routing import Route, Router, Routes
from kupala.testclient import TestClient
from kupala.websockets import WebSocket


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


@pytest.fixture()
def routes() -> Routes:
    return Routes()


@pytest.fixture()
def app() -> Kupala:
    return Kupala()


def test_get(app: Kupala) -> None:
    app.routes.get('/', view)
    client = TestClient(app)
    assert client.get('/').status_code == 200


def test_post(app: Kupala) -> None:
    app.routes.post('/', view)
    client = TestClient(app)
    assert client.post('/').status_code == 200


def test_get_or_post(app: Kupala) -> None:
    app.routes.get_or_post('/', view)
    client = TestClient(app)
    assert client.get('/').status_code == 200
    assert client.post('/').status_code == 200


def test_patch(app: Kupala) -> None:
    app.routes.patch('/', view)
    client = TestClient(app)
    assert client.patch('/').status_code == 200


def test_put(app: Kupala) -> None:
    app.routes.put('/', view)
    client = TestClient(app)
    assert client.put('/').status_code == 200


def test_delete(app: Kupala) -> None:
    app.routes.delete('/', view)
    client = TestClient(app)
    assert client.delete('/').status_code == 200


def test_head(app: Kupala) -> None:
    app.routes.head('/', view)
    client = TestClient(app)
    assert client.head('/').status_code == 200


def test_options(app: Kupala) -> None:
    app.routes.options('/', view)
    client = TestClient(app)
    assert client.options('/').status_code == 200


def test_websocket(app: Kupala) -> None:
    async def view(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("websocket data")
        await websocket.close(1001)

    app.routes.websocket("/ws", view)

    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "websocket data"


def test_mount(app: Kupala) -> None:
    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("ok")(scope, receive, send)

    app.routes.mount("/asgi", asgi)

    client = TestClient(app)
    response = client.get("/asgi")
    assert response.status_code == 200
    assert response.text == "ok"


def test_static(app: Kupala, tmp_path: str) -> None:
    styles = os.path.join(str(tmp_path), "styles.css")
    with open(styles, "w") as f:
        f.write("body {}")

    client = TestClient(app)
    app.routes.static("/static", tmp_path)

    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert response.text == "body {}"


def test_redirect(app: Kupala) -> None:
    app.routes.redirect("/profile", "/login")
    client = TestClient(app)
    response = client.get("/profile/", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_host(app: Kupala) -> None:
    with app.routes.host("api.example.com") as api:
        api.get("/users", view, name='users')

    client = TestClient(app)
    response = client.get("/users/", headers={"host": "api.example.com"})
    assert response.status_code == 200
    assert response.text == '/users'


def test_host_with_initial_routes(app: Kupala) -> None:
    app.routes.host("api.example.com", routes=[Route('/users', view)])

    client = TestClient(app)
    response = client.get("/users/", headers={"host": "api.example.com"})
    assert response.status_code == 200


def test_host_url_generation() -> None:
    routes = Routes()
    with routes.host("api.example.com") as api:
        api.get("/users", view, name='users')
    router = Router(routes=routes)
    assert router.url_path_for('users') == '/users'


def test_host_with_middleware(app: Kupala) -> None:
    call_stack: list[str] = []

    middleware = [
        Middleware(SampleMiddleware, callback=lambda: call_stack.append('one')),
        Middleware(SampleMiddleware, callback=lambda: call_stack.append('two')),
    ]
    with app.routes.host("api.example.com", middleware=middleware) as api:
        api.get("/users", view, name='users')

    client = TestClient(app)
    assert client.get('/users', headers={"host": "api.example.com"}).status_code == 200
    assert call_stack == ['one', 'two']  # check middleware call order


def test_group(app: Kupala) -> None:
    with app.routes.group("/admin") as admin:
        admin.get("/", view)
        admin.post("/create", view, name="admin-create")

    client = TestClient(app)
    response = client.get("/admin")
    assert response.status_code == 200
    assert response.text == '/admin/'

    response = client.post("/admin/create")
    assert response.status_code == 200
    assert response.text == '/admin/create'


def test_group_with_initial_routes(app: Kupala) -> None:
    app.routes.group(
        "/admin",
        routes=[
            Route("/", view),
            Route("/create/", view, name="admin-create", methods=["POST"]),
        ],
    )

    client = TestClient(app)
    response = client.get("/admin/")
    assert response.status_code == 200

    response = client.post("/admin/create/")
    assert response.status_code == 200


def test_group_url_generation() -> None:
    routes = Routes()
    with routes.group("/admin") as admin:
        admin.get("/users", view, name='admin_users')
        with admin.group('/category') as category:
            category.get('/items', view, name='category_items')

    router = Router(routes=routes)
    assert router.url_path_for('admin_users') == '/admin/users'
    assert router.url_path_for('category_items') == '/admin/category/items'


def test_group_with_middleware(app: Kupala) -> None:
    call_stack: list[str] = []

    middleware = [
        Middleware(SampleMiddleware, callback=lambda: call_stack.append('one')),
        Middleware(SampleMiddleware, callback=lambda: call_stack.append('two')),
    ]
    with app.routes.group("/admin", middleware=middleware) as api:
        api.get("/users", view, name='users')

    client = TestClient(app)
    assert client.get('/admin/users').status_code == 200
    assert call_stack == ['one', 'two']  # check middleware call order


def test_group_url_generation_with_middleware() -> None:
    call_stack: list[str] = []
    middleware = [Middleware(SampleMiddleware, callback=lambda: call_stack.append('one'))]
    middleware2 = [Middleware(SampleMiddleware, callback=lambda: call_stack.append('two'))]

    routes = Routes()
    with routes.group("/admin", middleware=middleware) as admin:
        admin.get("/users", view, name='admin_users')
        with admin.group('/category', middleware=middleware2) as category:
            category.get('/items', view, name='category_items')

    router = Router(routes=routes)
    assert router.url_path_for('admin_users') == '/admin/users'
    assert router.url_path_for('category_items') == '/admin/category/items'


@pytest.mark.parametrize('method', ['get', 'post', 'get_or_post', 'patch', 'put', 'delete', 'options', 'head', 'add'])
def test_route_specific_middleware(app: Kupala, method: str) -> None:
    call_stack: list[str] = []

    middleware = [
        Middleware(SampleMiddleware, callback=lambda: call_stack.append('one')),
        Middleware(SampleMiddleware, callback=lambda: call_stack.append('two')),
    ]

    fn = getattr(app.routes, method)
    if method == 'add':
        fn('/', view, methods=['GET'], middleware=middleware)
    else:
        fn('/', view, middleware=middleware)

    client = TestClient(app)
    client_method_name = method
    if client_method_name in {'add', 'get_or_post'}:
        client_method_name = 'get'
    client_method = getattr(client, client_method_name)
    assert client_method('/').status_code == 200
    assert call_stack == ['one', 'two']  # check middleware call order


def test_sizeable(routes: Routes) -> None:
    routes.get('/', view)
    routes.get('/two', view)
    assert len(routes) == 2


def test_iterable(routes: Routes) -> None:
    routes.get('/', view)
    routes.get('/two', view)
    assert len(list(routes)) == 2


def test_include_routes_instance(app: Kupala) -> None:
    routes = Routes()
    routes.get('/included', view)

    app.routes.include(routes)
    client = TestClient(app)
    assert client.get('/included').status_code == 200


def test_include_routes_list(app: Kupala) -> None:
    routes = [Route('/included', view)]

    app.routes.include(routes)
    client = TestClient(app)
    assert client.get('/included').status_code == 200
