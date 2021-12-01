from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.exceptions import ValidationError, default_validation_error_handler
from kupala.requests import Request


class FormErrorsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert 'session' in scope, 'FormErrorsMiddleware requires sessions enabled.'
        assert 'flash_messages' in scope, 'FormErrorsMiddleware requires flash messaging enabled.'

        try:
            await self.app(scope, receive, send)
        except ValidationError as exc:
            request = Request(scope, receive, send)
            response = await default_validation_error_handler(request, exc)
            await response(scope, receive, send)
