import typing
from starlette.routing import Mount, Route
from unittest import mock

from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes, include, include_all, route
from tests.conftest import ClientFactory


@route("/")
async def view(request: Request) -> None:  # pragma: nocover
    ...


def test_sizeable() -> None:
    routes = Routes([view, view])
    assert len(routes) == 2


def test_getitem() -> None:
    routes = Routes([view, view])
    assert routes[0] == view


def test_iterable(routes: Routes) -> None:
    routes = Routes([view, view])
    assert len(list(routes)) == 2


def test_route(test_client_factory: ClientFactory) -> None:
    @route("/")
    def index(_: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=[index])
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "ok"


def test_custom_request_class(test_client_factory: ClientFactory) -> None:
    class MyRequest(Request):
        ...

    @route("/")
    async def view(request: MyRequest) -> Response:
        return Response(request.__class__.__name__)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.text == "MyRequest"


def test_custom_request_class_alternate_varname(test_client_factory: ClientFactory) -> None:
    class MyRequest(Request):
        ...

    @route("/")
    async def view(req: MyRequest) -> Response:
        return Response(req.__class__.__name__)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.text == "MyRequest"


def test_generic_request_class(test_client_factory: ClientFactory) -> None:
    _t = typing.TypeVar("_t")

    class MyRequest(Request, typing.Generic[_t]):
        ...

    @route("/")
    async def view(request: MyRequest[int]) -> Response:
        return Response(request.__class__.__name__)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.text == "MyRequest"


def test_custom_request_class_with_other_deps(test_client_factory: ClientFactory) -> None:
    class Dep:
        ...

    def make_dep(request: Request) -> Dep:
        return Dep()

    DepInjection = typing.Annotated[Dep, make_dep]

    class MyRequest(Request):
        ...

    @route("/")
    async def view(req: MyRequest, dep: DepInjection) -> Response:
        return Response(req.__class__.__name__)

    client = test_client_factory(routes=[view])
    response = client.get("/")
    assert response.text == "MyRequest"


def example_view(request: Request) -> Response:
    return Response("ok")


def test_routes_add_route(test_client_factory: ClientFactory) -> None:
    route = Route("/", example_view)
    client = test_client_factory(routes=[route])
    assert client.get("/").text == "ok"


def test_routes_decorate_callable(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.route("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"


def test_routes_decorate_callable_multiple_times(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.route("/new")
    @routes.route("/edit")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/new").text == "ok"
    assert client.get("/edit").text == "ok"


def test_routes_is_callable(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"


def test_routes_is_iterable() -> None:
    routes = Routes()

    @routes("/")
    def example_view(request: Request) -> None:  # pragma: nocover
        ...

    assert list(routes)


def test_routes_is_sizeable() -> None:
    routes = Routes()

    @routes("/")
    def example_view(request: Request) -> None:  # pragma: nocover
        ...

    assert len(routes) == 1


def test_routes_repr() -> None:
    routes = Routes()
    assert repr(routes) == "<Routes: 0 routes>"


def test_routes_get(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.get("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"


def test_routes_post(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.post("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.post("/").text == "ok"


def test_routes_get_or_post(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.get_or_post("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").text == "ok"
    assert client.post("/").text == "ok"


def test_routes_put(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.put("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.put("/").text == "ok"


def test_routes_patch(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.patch("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.patch("/").text == "ok"


def test_routes_delete(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.delete("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.delete("/").text == "ok"


def test_routes_options(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.options("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.options("/").text == "ok"


def test_routes_accepts_routes_instance(test_client_factory: ClientFactory) -> None:
    routes = Routes()

    @routes.options("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    routes2 = Routes([routes])

    client = test_client_factory(routes=routes2)
    assert client.options("/").text == "ok"


def test_include() -> None:
    class _fake_routes:
        routes: list[Route] = mock.PropertyMock(return_value=Routes([Route("/", view)]))

    with mock.patch("importlib.import_module", lambda _: _fake_routes):
        routes = include("somemodule.routes")
        assert len(routes) == 1


def test_include_all() -> None:
    class _fake_routes:
        routes: list[Route] = mock.PropertyMock(return_value=Routes([Route("/", view)]))

    with mock.patch("importlib.import_module", lambda _: _fake_routes):
        routes = include_all(["somemodule.routes"])
        assert len(routes) == 1


def test_prefixed_routes(test_client_factory: ClientFactory) -> None:
    routes = Routes(prefix="/admin")

    @routes.get("/")
    def example_view(request: Request) -> Response:
        return Response("ok")

    client = test_client_factory(routes=routes)
    assert client.get("/").status_code == 404
    assert client.get("/admin").text == "ok"


def test_prefixed_routes_prepopulated(test_client_factory: ClientFactory) -> None:
    def example_view(request: Request) -> Response:
        return Response("ok")

    routes = Routes(prefix="/admin", routes=[Route("/", example_view)])

    client = test_client_factory(routes=routes)
    assert client.get("/").status_code == 404
    assert client.get("/admin").text == "ok"


def test_prefixed_routes_mount(test_client_factory: ClientFactory) -> None:
    def example_view(request: Request) -> Response:
        return Response("ok")

    routes = Routes(prefix="/admin", routes=[Mount("/", routes=[Route("/", example_view)])])

    client = test_client_factory(routes=routes)
    assert client.get("/").status_code == 404
    assert client.get("/admin").text == "ok"
