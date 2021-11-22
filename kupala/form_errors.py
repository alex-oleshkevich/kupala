from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.exceptions import ValidationError
from kupala.requests import Request
from kupala.responses import GoBackResponse, JSONResponse


class FormErrorsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert 'session' in scope, 'FormErrorsMiddleware requires sessions enabled.'
        assert 'flash_messages' in scope, 'FormErrorsMiddleware requires flash messaging enabled.'

        try:
            await self.app(scope, receive, send)
        except ValidationError as exc:
            request = Request(scope)
            if request.wants_json:
                json_response = JSONResponse({'message': exc.message, 'errors': exc.errors}, exc.status_code)
                await json_response(scope, receive, send)
                return

            await request.remember_form_data()
            request.set_form_errors(dict(exc.errors or {}))
            response = GoBackResponse(request)
            if exc.message:
                response = response.with_error(exc.message)
            await response(scope, receive, send)
