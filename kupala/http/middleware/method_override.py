from starlette.types import ASGIApp, Receive, Scope, Send

BODY_PARAM = '_method'


class MethodOverrideMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':  # pragma: nocover
            return await self.app(scope, receive, send)

        if scope['method'] == 'POST':
            assert (
                'body_params' in scope
            ), 'MethodOverrideMiddleware depends on RequestParserMiddleware which is not installed.'
            override = scope.get('body_params', {}).get(BODY_PARAM, '')
            if override:
                scope['original_method'] = scope['method']
                scope['method'] = override.upper()

        await self.app(scope, receive, send)
