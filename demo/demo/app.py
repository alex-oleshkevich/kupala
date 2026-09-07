import itertools
import json
import typing

import anyio

from kupala.applications import Kupala
from kupala.dependencies import Value
from kupala.errors import BadRequestError
from kupala.middleware import CallNext
from kupala.requests import Request
from kupala.responses import Response, ServerSentEvent, response
from kupala.routing import Routes

routes = Routes()


class User: ...


class RuleEnforcer: ...


type Guard = typing.Annotated[RuleEnforcer, Value("guard")]
type CurrentUser = typing.Annotated[User, Value("user")]


async def app_middleware(request: Request, call_next: CallNext) -> Response:
    print("APP")
    response = await call_next(request)
    print("AFTER APP")
    return response


async def example_middleware(request: Request, call_next: CallNext) -> Response:
    print("APP REG")
    response = await call_next(request)
    print("AFTER APP_REG")
    return response


@routes.get("/")
@routes.get("/overview", name="overview")
async def index_view(request: Request) -> Response:
    return response(request).text("hi")


@routes.get("/dependency")
async def dependency_view(request: Request, user: CurrentUser, guard: Guard) -> Response:
    return response(request).text(f"{user} - {guard}")


@routes.get("/error")
async def http_error_view(request: Request) -> Response:
    raise BadRequestError()


@routes.get("/unhandled")
async def unhandled_error_view(request: Request) -> Response:
    raise ValueError("boom")


@routes.post("/post")
async def post_view(request: Request) -> Response:
    return response(request).text("ok")


@routes.get("/sse", name="sse")
async def sse_view(request: Request) -> Response:
    async def ticks() -> typing.AsyncIterator[ServerSentEvent]:
        try:
            for tick in itertools.count(1):
                yield ServerSentEvent(event="tick", id=str(tick), data=json.dumps({"tick": tick}))
                await anyio.sleep(1)
        finally:
            # the generator is closed when the browser goes away, so the stream never leaks
            print("SSE CLIENT GONE")

    return response(request).sse(ticks(), keepalive_interval=5.0)


app = Kupala(
    __name__,
    debug=True,
    routes=routes,
    middleware=[app_middleware, example_middleware],
)
