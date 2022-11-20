from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import Routes, route


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
