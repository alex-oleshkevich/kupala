import contextlib
import typing

from kupala.app import Kupala
from kupala.config import Env
from kupala.exceptions import BadRequestError, ValidationError
from kupala.requests import Request, Websocket
from kupala.responses import Response, responses
from kupala.routing import RouteGroup
from kupala.validation import ErrorBag

env = Env(env_files=[".env", ".env.local"])


@contextlib.asynccontextmanager
async def create_dbpool(app: Kupala) -> typing.AsyncIterator[dict[str, typing.Any]]:
    yield {"dbpool": "dbpoolinstance"}


routes = RouteGroup()


@routes.get("/", name="home")
@routes.get("/home")
def index_view(request: Request) -> Response:
    print(request.state)
    return Response()


@routes.get_or_post("/login")
async def login_view(request: Request) -> Response:
    data = await request.parse(dict[str, str])

    errors = ErrorBag()
    email = data.get("email", "")
    if not email:
        errors.append("email", "Email is required.")

    password = data.get("password", "")
    if not password:
        errors.append("password", "Password is required.")

    if errors:
        raise ValidationError(errors=errors, problem_type="login_failure")

    if password != "password":
        raise BadRequestError("Invalid email or password")

    if email != "admin":
        raise BadRequestError("")

    return responses(request).redirect_to_route("home")


@routes.get("/version")
def version_view(_request: Request) -> str:
    return "0.100.0"


@routes.get("/health")
def health_view(_request: Request) -> tuple[str, int]:
    return "ok", 200


@routes.get("/status")
def three_tuple_view(_request: Request) -> tuple[str, int, dict[str, str]]:
    return "ok", 200, {"x-key": "x-value"}


@routes.websocket("/ws")
async def ws_view(ws: Websocket) -> None:
    pass


app = Kupala(routes=routes, lifespan=[create_dbpool])
