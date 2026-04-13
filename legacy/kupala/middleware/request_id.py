import uuid
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pragma: no cover
            return await self.app(scope, receive, send)

        connection = HTTPConnection(scope, receive)
        request_id = connection.headers.get("x-request-id", self.generate_id())
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        async def sender(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message["headers"])
                headers["x-request-id"] = request_id
            await send(message)

        await self.app(scope, receive, sender)

    def generate_id(self) -> str:
        return str(uuid.uuid4()).replace("-", "")
