import typing
from starlette import status
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LargeEntityError(ValueError):
    pass


class RequestLimitMiddleware:
    """
    Limit request body to a value of max_body_size.

    When request body exceeds the limit then 413 response returned.
    """

    def __init__(self, app: ASGIApp, max_body_size: typing.Optional[int] = 2048) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        total_len = 0
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def receive_wrapper() -> Message:
            message = await receive()
            if message["type"] != "http.request" or self.max_body_size is None:
                return message

            nonlocal total_len
            body = message.get("body", b"")
            total_len += len(body)
            if total_len > self.max_body_size:
                raise LargeEntityError()
            return message

        try:
            await self.app(scope, receive_wrapper, send)
        except LargeEntityError:
            response = PlainTextResponse("Entity Too Large", status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
            await response(scope, receive, send)
