from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import Request
from kupala.http.middleware import Middleware
from kupala.http.routing import Mount, static_files


def example_middleware(app: ASGIApp) -> ASGIApp:
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        await app(scope, receive, send)

    return middleware


def example_guard(request: Request) -> None:
    pass


def test_static_files() -> None:
    route = static_files(
        path="/static",
        directory="/statics",
        name="static",
        html=False,
        check_dir=False,
        middleware=[Middleware(example_middleware)],
        guards=[example_guard],
    )
    assert isinstance(route, Mount)
