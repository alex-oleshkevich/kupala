from starlette.routing import Route

from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes, route
from tests.conftest import TestClientFactory


@route("/")
async def view(request: Request) -> Response:
    return Response(request.url.path)


@route("/users", name="users")
async def users_view(request: Request) -> Response:
    return Response(request.url.path)


def test_sizeable() -> None:
    routes = Routes([view, view])
    assert len(routes) == 2


def test_iterable(routes: Routes) -> None:
    routes = Routes([view, view])
    assert len(list(routes)) == 2


def test_route(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def index(_: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=[index])
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "ok"


def test_custom_request_class(test_client_factory: TestClientFactory) -> None:
    class MyRequest(Request):
        ...

    @route("/")
    async def view(request: MyRequest) -> Response:
        return Response(request.__class__.__name__)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.text == "MyRequest"


def example_view(request: Request) -> Response:
    return Response("ok")


def test_routes_add_route(test_client_factory: TestClientFactory) -> None:
    route = Route("/", example_view)
    client = test_client_factory(routes=[route])
    assert client.get("/").text == "ok"


def test_routes_decorate_callable(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.route("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"


def test_routes_decorate_callable_multiple_times(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.route("/new")
    @routes.route("/edit")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/new").text == "ok"
    assert client.get("/edit").text == "ok"


def test_routes_is_callable(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"


def test_routes_is_iterable() -> None:
    routes = Routes()

    @routes("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    assert list(routes)


def test_routes_is_sizeable() -> None:
    routes = Routes()

    @routes("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    assert len(routes) == 1


def test_routes_repr() -> None:
    routes = Routes()
    assert repr(routes) == "<Routes: 0 routes>"


def test_routes_get(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.get_or_post("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"


def test_routes_post(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.get_or_post("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.post("/").text == "ok"


def test_routes_get_or_post(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.get_or_post("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"
    assert client.post("/").text == "ok"


def test_routes_put(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.put("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.put("/").text == "ok"


def test_routes_patch(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.patch("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.patch("/").text == "ok"


def test_routes_delete(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.delete("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.delete("/").text == "ok"


def test_routes_options(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.options("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.options("/").text == "ok"


def test_routes_accepts_routes_instance(test_client_factory: TestClientFactory) -> None:
    routes = Routes()

    @routes.options("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    routes2 = Routes([routes])

    client = test_client_factory(routes=routes2)
    assert client.options("/").text == "ok"
