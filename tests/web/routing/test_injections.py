import dataclasses

from kupala.dependencies import Inject, inject
from kupala.http import Request, Response, route
from tests.conftest import TestClientFactory


def test_injects_dependencies(test_client_factory: TestClientFactory) -> None:
    @dataclasses.dataclass
    class Db:
        name: str

    def get_db(request: Request) -> Db:
        return Db(name="postgres")

    async def get_async_db(request: Request) -> Db:
        return Db(name="async_postgres")

    @route("/user/{id}")
    @inject(db=get_db, async_db=get_async_db, via_class=Inject(get_db))
    async def view(request: Request, db: Db, async_db: Db, via_class: Db, id: str) -> Response:
        return Response(f"{db.name}_{async_db.name}_{via_class.name}_{id}")

    client = test_client_factory(routes=[view])
    response = client.get("/user/42")
    assert response.text == "postgres_async_postgres_postgres_42"
