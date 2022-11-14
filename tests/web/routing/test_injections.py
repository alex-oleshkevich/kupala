import dataclasses

import pytest
import typing

from kupala.application import Kupala
from kupala.dependencies import Injector
from kupala.http import Request, Response, route
from kupala.testclient import TestClient


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

    app = Kupala(debug=True, routes=[view], dependencies=injector)
    client = TestClient(app=app)
    response = client.get("/")
    assert response.text == "postgres"


def test_injects_async_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: ADb) -> Response:
        return Response(db.name)

    app = Kupala(routes=[view], dependencies=injector)
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "postgres"


def test_cached_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: CachedDb) -> Response:
        return Response(str(id(db)))

    app = Kupala(routes=[view], dependencies=injector)
    client = TestClient(app)
    assert client.get("/").text == client.get("/").text


def test_cached_async_dependencies(injector: Injector) -> None:
    @route("/")
    async def view(request: Request, db: ACachedDb) -> Response:
        return Response(str(id(db)))

    app = Kupala(routes=[view], dependencies=injector)
    client = TestClient(app)
    assert client.get("/").text == client.get("/").text


def test_injects_dependencies_and_path_params(injector: Injector) -> None:
    @route("/user/{id}")
    async def view(request: Request, db: Db, id: str) -> Response:
        return Response(db.name + id)

    app = Kupala(routes=[view], dependencies=injector)
    client = TestClient(app)
    response = client.get("/user/42")
    assert response.text == "postgres42"


def test_handles_untyped_path_params(injector: Injector) -> None:
    @route("/user/{id}")
    async def view(request: Request, db: Db, id) -> Response:  # type: ignore[no-untyped-def]
        return Response(db.name + id)

    app = Kupala(routes=[view], dependencies=injector)
    client = TestClient(app)
    response = client.get("/user/42")
    assert response.text == "postgres42"


def test_not_fail_for_optional_path_params(injector: Injector) -> None:
    @route("/user")
    def view(request: Request, db: Db, id: str | None = None) -> Response:
        return Response("ok")

    app = Kupala(routes=[view], dependencies=injector)
    client = TestClient(app)
    response = client.get("/user")
    assert response.text == "ok"
