from starlette.exceptions import HTTPException, WebSocketException
from starlette.types import ExceptionHandler
from starlette.websockets import WebSocket

from kupala.errors import BaseHTTPError
from kupala.requests import Request
from kupala.responses import Response

type ErrorHandler = ExceptionHandler


async def http_error_handler(request: Request, exc: Exception) -> Response:
    """Automatically handle HTTP errors."""
    match exc:
        case BaseHTTPError():
            print("BASE", exc)
        case HTTPException():
            print("STARLETTE", exc)

    # render html page
    # render json -> configurable! problemdetail by default
    return Response(f"ok: {exc}")


async def server_error_handler(request: Request, exc: Exception) -> Response:
    """Render unhandled application exception. Prints debug page in debug mode or 500 error page."""
    if request.app.debug:
        return Response(f"internal server error: {exc}", status_code=500)
    return Response("internal server error", status_code=500)


async def websocket_error_handler(websocket: WebSocket, exc: Exception) -> None:
    assert isinstance(exc, WebSocketException)
    await websocket.close(code=exc.code, reason=exc.reason)  # pragma: no cover


class ErrorHandlers:
    def __init__(self, handlers: dict[type[Exception], ErrorHandler]) -> None:
        self._handlers = handlers

    def merge(self, handlers: dict[type[Exception], ErrorHandler]) -> None:
        self._handlers.update(handlers)

    def lookup_for(self, exc: Exception) -> ErrorHandler | None:
        for cls in type(exc).__mro__:
            if cls in self._handlers:
                return self._handlers[cls]
        return None
