from kupala.applications import Kupala
from kupala.errors import BadRequestError
from kupala.middleware import CallNext
from kupala.requests import Request
from kupala.responses import Response, response
from kupala.routing import Routes

routes = Routes()


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


@routes.get("/error")
async def http_error_view(request: Request) -> Response:
    raise BadRequestError()


@routes.get("/unhandled")
async def unhandled_error_view(request: Request) -> Response:
    raise ValueError("boom")


@routes.post("/post")
async def post_view(request: Request) -> Response:
    return response(request).text("ok")


app = Kupala(
    __name__,
    debug=True,
    routes=routes,
    middleware=[app_middleware, example_middleware],
)
