import typing
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import Request

BODY_PARAM = '_method'


class MethodOverrideMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':  # pragma: nocover
            return await self.app(scope, receive, send)

        if scope['method'] == 'POST':
            request = Request(scope, receive)
            form_data = await request.form()
            override = typing.cast(str, form_data.get(BODY_PARAM, ''))
            if override:
                scope['original_method'] = scope['method']
                scope['method'] = override.upper()

        await self.app(scope, receive, send)
