from kupala.app import Kupala
from kupala.requests import Request, Websocket
from kupala.responses import Response
from kupala.routing import RouteGroup

routes = RouteGroup()


@routes.get("/")
@routes.get("/home")
def index_view(_request: Request) -> Response:
    return Response()


@routes.get("/version")
def version_view(_request: Request) -> str:
    return "0.100.0"


@routes.get("/health")
def health_view(_request: Request) -> tuple[str, int]:
    return "ok", 200


@routes.get("/health")
def three_tuple_view(_request: Request) -> tuple[str, int, dict[str, str]]:
    return "ok", 200, {"x-key": "x-value"}


@routes.websocket("/ws")
async def ws_view(ws: Websocket) -> None:
    pass


app = Kupala(routes=routes)
