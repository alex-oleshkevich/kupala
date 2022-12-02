import dataclasses

import pytest
import typing
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.testclient import TestClient

from kupala.dependencies import DiMiddleware, Injector
from kupala.requests import Request
from kupala.responses import Response
from kupala.routing import route


@dataclasses.dataclass
class Db:
    name: str


class ADb(Db):
    ...


class CachedDb(Db):
    ...


class ACachedDb(Db):
    ...


@pytest.fixture
def sync_db_factory() -> typing.Callable:
    def get_db(request: Request) -> Db:
        return Db(name="postgres")

    return get_db


@pytest.fixture
def async_db_factory() -> typing.Callable:
    async def get_db(request: Request) -> Db:
        return Db(name="postgres")

    return get_db


@pytest.fixture
def injector(sync_db_factory: typing.Callable, async_db_factory: typing.Callable) -> Injector:
    injector = Injector()
    injector.add_dependency(Db, sync_db_factory)
    injector.add_dependency(ADb, async_db_factory)
    injector.add_dependency(CachedDb, sync_db_factory, cached=True)
    injector.add_dependency(ACachedDb, async_db_factory, cached=True)
    return injector


def test_injects_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: Db) -> Response:
        return Response(db.name)

    app = Starlette(
        debug=True,
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "postgres"


def test_injects_async_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: ADb) -> Response:
        return Response(db.name)

    app = Starlette(
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "postgres"


def test_cached_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: CachedDb) -> Response:
        return Response(str(id(db)))

    app = Starlette(
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app)
    assert client.get("/").text == client.get("/").text


def test_cached_async_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: ACachedDb) -> Response:
        return Response(str(id(db)))

    app = Starlette(
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app)
    assert client.get("/").text == client.get("/").text


def annotated_db_factory(request: Request) -> Db:
    return Db("annotated")


AnnotatedDb = typing.Annotated[Db, annotated_db_factory]


def test_annotation_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: AnnotatedDb) -> Response:
        return Response(db.name)

    app = Starlette(
        debug=True,
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "annotated"


def test_injects_dependencies_and_path_params(injector: Injector) -> None:
    @route("/user/{id}")
    async def view(request: Request, db: Db, id: str) -> Response:
        return Response(db.name + id)

    app = Starlette(
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app)
    response = client.get("/user/42")
    assert response.text == "postgres42"


def test_handles_untyped_path_params(injector: Injector) -> None:
    @route("/user/{id}")
    async def view(request: Request, db: Db, id) -> Response:  # type: ignore[no-untyped-def]
        return Response(db.name + id)

    app = Starlette(
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app)
    response = client.get("/user/42")
    assert response.text == "postgres42"


def test_not_fail_for_optional_path_params(injector: Injector) -> None:
    @route("/user")
    def view(request: Request, db: Db, id: str | None = None) -> Response:
        return Response("ok")

    app = Starlette(
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app)
    response = client.get("/user")
    assert response.text == "ok"


def test_custom_request_class(injector: Injector) -> None:
    class MyRequest(Request):
        ...

    @route("/")
    async def view(request: MyRequest) -> Response:
        return Response(request.__class__.__name__)

    app = Starlette(
        debug=True,
        routes=[view],
        middleware=[
            Middleware(DiMiddleware, injector=injector),
        ],
    )
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "MyRequest"
