from unittest import mock

from starlette.types import ASGIApp
from starlette.websockets import WebSocket

from kupala.middlewares.base import BaseHTTPMiddleware, RequestResponseEndpoint
from kupala.requests import Request
from kupala.responses import JSONResponse, Response


class _Example(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, fn: mock.MagicMock):
        super().__init__(app)
        self.fn = fn

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        self.fn(request)
        return await call_next(request)


def view(request: Request):
    return JSONResponse(
        {
            "method": request.method,
            "path_params": dict(request.path_params),
        }
    )


async def ws_view(ws: WebSocket) -> None:
    await ws.accept()


def test_uses_request_from_scope(test_client, app):
    spy = mock.MagicMock()
    app.middleware.use(_Example, fn=spy)
    app.routes.get("/", view)
    test_client.get("/")

    assert isinstance(spy.call_args[0][0], Request)


def test_ignores_non_http_types(test_client, app):
    spy = mock.MagicMock()
    app.middleware.use(_Example, fn=spy)
    app.routes.websocket("/ws", ws_view)
    test_client.websocket_connect("/ws")
    assert spy.call_count == 0
