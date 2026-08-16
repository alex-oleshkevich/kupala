from starlette.exceptions import HTTPException, WebSocketException
from starlette.types import ExceptionHandler
from starlette.websockets import WebSocket

from kupala.requests import Request
from kupala.responses import Response

type ErrorHandler = ExceptionHandler


async def http_error_handler(request: Request, exc: Exception) -> Response:
    """Automatically handle HTTP errors."""
    assert isinstance(exc, HTTPException)
    # render html page
    # render json -> configurable! problemdetail by default
    return Response(
        f"{exc.status_code}: {exc.detail}",
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def server_error_handler(request: Request, exc: Exception) -> Response:
    """Render unhandled application exception. Prints debug page in debug mode or 500 error page."""
    if request.app.debug:
        return Response(f"internal server error: {exc}", status_code=500)
    return Response("internal server error", status_code=500)


async def websocket_error_handler(websocket: WebSocket, exc: Exception) -> None:
    assert isinstance(exc, WebSocketException)
    await websocket.close(code=exc.code, reason=exc.reason)  # pragma: no cover
