from starlette.exceptions import HTTPException, WebSocketException
from starlette.types import ExceptionHandler
from starlette.websockets import WebSocket

from kupala.requests import Request
from kupala.responses import Response

type ErrorHandler = ExceptionHandler

# error text often echoes user input, and a body without a content type is MIME-sniffed
NO_SNIFF_HEADERS = {"x-content-type-options": "nosniff"}


async def http_error_handler(request: Request, exc: Exception) -> Response:
    """Automatically handle HTTP errors."""
    assert isinstance(exc, HTTPException)
    # render html page
    # render json -> configurable! problemdetail by default
    return Response(
        f"{exc.status_code}: {exc.detail}",
        status_code=exc.status_code,
        headers={**(exc.headers or {}), **NO_SNIFF_HEADERS},
        media_type="text/plain",
    )


async def server_error_handler(request: Request, exc: Exception) -> Response:
    """Render unhandled application exception. Prints debug page in debug mode or 500 error page."""
    detail = f"internal server error: {exc}" if request.app.debug else "internal server error"
    return Response(
        detail,
        status_code=500,
        headers=NO_SNIFF_HEADERS,
        media_type="text/plain",
    )


async def websocket_error_handler(websocket: WebSocket, exc: Exception) -> None:
    assert isinstance(exc, WebSocketException)
    await websocket.close(code=exc.code, reason=exc.reason)
