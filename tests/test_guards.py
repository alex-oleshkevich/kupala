from starlette.applications import Starlette
from starlette.responses import Response
from starlette.testclient import TestClient

from kupala.guards import NextGuard
from kupala.requests import Request
from kupala.routing import route


async def guard_one(request: Request, call_next: NextGuard) -> Response:
    request.scope.setdefault("guards", [])
    request.scope["guards"].append("one")

    return await call_next(request)


async def guard_two(request: Request, call_next: NextGuard) -> Response:
    request.scope.setdefault("guards", [])
    request.scope["guards"].append("two")
    return await call_next(request)


def test_no_guards() -> None:
    @route("/", guards=[])
    async def view() -> Response:
        return Response("ok")

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "ok"


def test_calls_one_guard() -> None:
    @route("/", guards=[guard_one])
    async def view(request: Request) -> Response:
        return Response(str(request.scope["guards"]))

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "['one']"


def test_calls_guard_chain() -> None:
    @route("/", guards=[guard_one, guard_two])
    async def view(request: Request) -> Response:
        return Response(str(request.scope["guards"]))

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "['one', 'two']"
