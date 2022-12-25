import dataclasses

from starlette.middleware import Middleware
from starlette.requests import HTTPConnection
from starlette.responses import Response

from kupala.authentication import AuthenticationMiddleware, AuthToken, LoginState, UserLike
from kupala.injectables import JSON, Auth, CurrentUser, FormData, FromQuery
from kupala.routing import route
from tests.conftest import TestClientFactory


def test_from_query(test_client_factory: TestClientFactory) -> None:
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


def test_json_body(test_client_factory: TestClientFactory) -> None:
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


def test_form_data(test_client_factory: TestClientFactory) -> None:
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


def test_current_user(test_client_factory: TestClientFactory) -> None:
    @dataclasses.dataclass
    class User:
        name: str = "root"

    @route("/")
    async def view(user: CurrentUser[User]) -> Response:
        return Response(user.name)

    async def dummy_authenticator(connection: HTTPConnection) -> AuthToken | None:
        return AuthToken(user=User(), state=LoginState.FRESH)

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[dummy_authenticator]),
        ],
    )
    response = client.get("/")
    assert response.text == "root"


def test_auth_token(test_client_factory: TestClientFactory) -> None:
    @dataclasses.dataclass
    class User(UserLike):
        name: str = "root"

    @route("/")
    async def view(auth: Auth[User]) -> Response:
        return Response(auth.user.name)

    async def dummy_authenticator(connection: HTTPConnection) -> AuthToken | None:
        return AuthToken(user=User(), state=LoginState.FRESH)

    client = test_client_factory(
        routes=[view],
        middleware=[
            Middleware(AuthenticationMiddleware, authenticators=[dummy_authenticator]),
        ],
    )
    response = client.get("/")
    assert response.text == "root"
