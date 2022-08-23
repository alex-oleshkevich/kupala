from kupala.http import route
from kupala.http.requests import Request
from kupala.http.responses import Response
from kupala.http.routing import Routes


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
