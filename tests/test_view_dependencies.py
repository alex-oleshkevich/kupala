import dataclasses

import contextlib
import pytest
import typing
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.testclient import TestClient

from kupala.requests import Request
from kupala.routing import InjectionError, route
from tests.conftest import ClientFactory


@dataclasses.dataclass
class Db:
    name: str


def annotated_db_factory(request: Request) -> Db:
    return Db("annotated")


async def async_annotated_db_factory(request: Request) -> Db:
    return Db("async_annotated")


AnnotatedDb = typing.Annotated[Db, annotated_db_factory]
AsyncAnnotatedDb = typing.Annotated[Db, async_annotated_db_factory]


def test_injects_path_params(test_client_factory: ClientFactory) -> None:
    """It should inject path param via function arguments."""

    @route("/users/{id}")
    async def view(request: Request, id: str) -> Response:
        return Response(id)

    client = test_client_factory(routes=[view])
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.text == "1"


def test_ignores_path_param_if_not_requested(test_client_factory: ClientFactory) -> None:
    """It should not inject path param if view callable does not require requests it."""

    @route("/{user:int}")
    async def view() -> Response:
        return Response("ok")

    client = test_client_factory(routes=[view])
    response = client.get("/1")
    assert response.text == "ok"


def test_annotation_dependencies() -> None:
    """It should inject dependency with factory declared using typing.Annotated."""

    @route("/")
    async def view(db: AnnotatedDb) -> Response:
        return Response(db.name)

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "annotated"


def test_annotated_async_dependency_factory() -> None:
    """
    It should inject dependency with factory declared using typing.Annotated.

    Async version.
    """

    @route("/")
    async def view(db: AsyncAnnotatedDb) -> Response:
        return Response(db.name)

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "async_annotated"


def test_injects_multiple_annotated_dependency_factories() -> None:
    """It should inject multiple dependencies declared using typing.Annotated."""

    @route("/")
    async def view(async_db: AsyncAnnotatedDb, sync_db: AnnotatedDb) -> Response:
        return Response(f"{sync_db.name}-{async_db.name}")

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "annotated-async_annotated"


def test_injects_annotated_dependency_factories_with_dependencies() -> None:
    async def make_dep_one(request: Request) -> str:
        return "one"

    DepOne = typing.Annotated[str, make_dep_one]

    def make_dep_two(request: Request, dep: DepOne) -> str:
        return dep + "two"

    DepTwo = typing.Annotated[str, make_dep_two]

    def make_dep_three(request: Request, dep: DepOne, dep2: DepTwo) -> str:
        return dep + dep2

    DepThree = typing.Annotated[str, make_dep_three]

    @route("/")
    async def view(dep: DepThree) -> Response:
        return Response(dep)

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "oneonetwo"


def test_injects_yield_dependencies() -> None:
    @contextlib.contextmanager
    def make_dep_one(request: Request) -> typing.Generator[str, None, None]:
        yield "one"

    DepOne = typing.Annotated[str, make_dep_one]

    @route("/")
    async def view(dep: DepOne) -> Response:
        return Response(dep)

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "one"


def test_injects_async_yield_dependencies() -> None:
    @contextlib.asynccontextmanager
    async def make_dep_one(request: Request) -> typing.AsyncGenerator[str, None]:
        yield "one"

    DepOne = typing.Annotated[str, make_dep_one]

    @route("/")
    async def view(dep: DepOne) -> Response:
        return Response(dep)

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "one"


def test_injects_nested_yield_dependencies() -> None:
    @contextlib.asynccontextmanager
    async def make_dep_one(request: Request) -> typing.AsyncGenerator[str, None]:
        yield "one"

    DepOne = typing.Annotated[typing.AsyncContextManager[str], make_dep_one]

    @contextlib.asynccontextmanager
    async def make_dep_two(request: Request, dep: DepOne) -> typing.AsyncGenerator[str, None]:
        async with dep as value:
            yield value + "two"

    DepTwo = typing.Annotated[str, make_dep_two]

    @route("/")
    async def view(dep: DepTwo) -> Response:
        return Response(dep)

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "onetwo"


def test_annotation_dependencies_and_path_params() -> None:
    """It should inject dependency with factory declared using typing.Annotated and inject any requested path params."""

    @route("/{user_id:int}")
    async def view(db: AnnotatedDb, user_id: int) -> Response:
        return Response(f"{db.name}_{user_id}")

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/42")
    assert response.text == "annotated_42"


ReturnsNone = typing.Annotated[int, lambda _: None]


def test_optional_annotation_dependencies() -> None:
    """It should raise InjectionError if dependency factory returns None and argument is not optional."""

    @route("/")
    async def view(value: ReturnsNone) -> Response:
        return Response("ok")

    with pytest.raises(InjectionError):
        app = Starlette(debug=True, routes=[view])
        client = TestClient(app=app)
        response = client.get("/")
        assert response.text == "ok"


def test_optional_annotation_dependencies_with_default_value() -> None:
    """It should inject None if dependency factory return None and argument is optional."""

    @route("/")
    async def view(value: ReturnsNone | None = None) -> Response:
        return Response("ok" if value is None else "fail")

    app = Starlette(debug=True, routes=[view])
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "ok"


def test_handles_untyped_path_params() -> None:
    """It should not fail if view argument has no type but present in path params."""

    @route("/user/{user_id}")
    async def view(request: Request, user_id) -> Response:  # type: ignore[no-untyped-def]
        return Response(user_id)

    app = Starlette(routes=[view])
    client = TestClient(app)
    response = client.get("/user/42")
    assert response.text == "42"
