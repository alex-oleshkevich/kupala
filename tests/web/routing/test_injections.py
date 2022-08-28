import dataclasses

from kupala.http import Request, Response, route
from tests.conftest import TestClientFactory


@dataclasses.dataclass
class Db:
    name: str


def test_injects_dependencies(test_client_factory: TestClientFactory) -> None:
    def get_db(request: Request) -> Db:
        return Db(name="postgres")

    @route("/")
    async def view(request: Request, db: Db) -> Response:
        return Response(db.name)

    client = test_client_factory(routes=[view])
    client.app.add_dependency(Db, get_db)
    response = client.get("/")
    assert response.text == "postgres"


def test_injects_async_dependencies(test_client_factory: TestClientFactory) -> None:
    async def get_db(request: Request) -> Db:
        return Db(name="postgres")

    @route("/")
    async def view(request: Request, db: Db) -> Response:
        return Response(db.name)

    client = test_client_factory(routes=[view])
    client.app.add_dependency(Db, get_db)
    response = client.get("/")
    assert response.text == "postgres"


def test_cached_dependencies(test_client_factory: TestClientFactory) -> None:
    def get_db(request: Request) -> Db:
        return Db(name="postgres")

    @route("/")
    async def view(request: Request, db: Db) -> Response:
        return Response(str(id(db)))

    client = test_client_factory(routes=[view])
    client.app.add_dependency(Db, get_db, cached=True)
    assert client.get("/").text == client.get("/").text


def test_cached_async_dependencies(test_client_factory: TestClientFactory) -> None:
    async def get_db(request: Request) -> Db:
        return Db(name="postgres")

    @route("/")
    async def view(request: Request, db: Db) -> Response:
        return Response(str(id(db)))

    client = test_client_factory(routes=[view])
    client.app.add_dependency(Db, get_db, cached=True)
    assert client.get("/").text == client.get("/").text


def test_injects_dependencies_and_path_params(test_client_factory: TestClientFactory) -> None:
    async def get_db(request: Request) -> Db:
        return Db(name="postgres")

    @route("/user/{id}")
    async def view(request: Request, db: Db, id: str) -> Response:
        return Response(db.name + id)

    client = test_client_factory(routes=[view])
    client.app.add_dependency(Db, get_db)
    response = client.get("/user/42")
    assert response.text == "postgres42"


def test_handles_untyped_path_params(test_client_factory: TestClientFactory) -> None:
    async def get_db(request: Request) -> Db:
        return Db(name="postgres")

    @route("/user/{id}")
    async def view(request: Request, db: Db, id) -> Response:  # type: ignore[no-untyped-def]
        return Response(db.name + id)

    client = test_client_factory(routes=[view])
    client.app.add_dependency(Db, get_db)
    response = client.get("/user/42")
    assert response.text == "postgres42"
