import dataclasses

import pytest
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import Response

from kupala.injectables import JSON, CurrentUser, FormData, FromPath, FromQuery
from kupala.routing import route
from tests.conftest import ClientFactory, User
from tests.utils import DummyBackend


def test_from_query(test_client_factory: ClientFactory) -> None:
    @dataclasses.dataclass
    class CustomQueryParams:
        search: str = ""
        page: int = 1

    @route("/")
    async def view(query: FromQuery[CustomQueryParams]) -> Response:
        return Response(query.__class__.__name__)

    @route("/param")
    async def param_view(query: FromQuery[CustomQueryParams]) -> Response:
        return Response(query.search)

    client = test_client_factory(routes=[view, param_view])
    response = client.get("/")
    assert response.text == CustomQueryParams.__name__

    response = client.get("/param?search=query")
    assert response.text == "query"


def test_json_body(test_client_factory: ClientFactory) -> None:
    @dataclasses.dataclass
    class BodyPayload:
        search: str = ""
        page: int = 1

    @route("/", methods=["post"])
    async def view(body: JSON[BodyPayload]) -> Response:
        return Response(body.__class__.__name__)

    client = test_client_factory(routes=[view])
    response = client.post("/", json={"search": "value"})
    assert response.text == BodyPayload.__name__


def test_form_data(test_client_factory: ClientFactory) -> None:
    @dataclasses.dataclass
    class BodyPayload:
        search: str = ""
        page: int = 1

    @route("/", methods=["post"])
    async def view(body: FormData[BodyPayload]) -> Response:
        return Response(body.__class__.__name__)

    client = test_client_factory(routes=[view])
    response = client.post("/", data={"search": "value"})
    assert response.text == BodyPayload.__name__


def test_current_user(test_client_factory: ClientFactory, user: User) -> None:
    @route("/")
    async def view(user: CurrentUser[User]) -> Response:
        return Response(user.username)

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=DummyBackend(user)),
        ],
    )
    response = client.get("/")
    assert response.text == "root"


def test_from_path(test_client_factory: ClientFactory) -> None:
    @route("/users/{id}")
    async def view(id: FromPath[int]) -> Response:
        return Response(str(id) + str(type(id).__name__))

    client = test_client_factory(routes=[view])
    response = client.get("/users/1")
    assert response.text == "1int"


def test_from_path_with_optional(test_client_factory: ClientFactory) -> None:
    @route("/users")
    async def view(id: FromPath[int] | None = None) -> Response:
        return Response(str(id))

    client = test_client_factory(routes=[view])
    response = client.get("/users")
    assert response.text == "None"


def test_from_path_required(test_client_factory: ClientFactory) -> None:
    @route("/users")
    async def view(id: FromPath[int]) -> None:  # pragma: nocover
        ...

    with pytest.raises(ValueError, match="no default value defined"):
        client = test_client_factory(routes=[view])
        client.get("/users")
