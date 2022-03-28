import uuid
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':  # pragma: nocover
            return await self.app(scope, receive, send)

        connection = HTTPConnection(scope, receive)
        request_id = connection.headers.get('x-request-id', self.generate_id())
        scope['request_id'] = request_id

        await self.app(scope, receive, send)

    def generate_id(self) -> str:
        return str(uuid.uuid4()).replace('-', '')
