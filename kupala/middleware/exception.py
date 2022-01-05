import inspect
import jinja2
import typing as t
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as BaseHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.exceptions import HTTPException, ValidationError
from kupala.requests import Request
from kupala.responses import GoBackResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response

E = t.TypeVar('E', bound=Exception)
ErrorHandler = t.Callable[[Request, E], t.Any]
_renderer = jinja2.Environment(loader=jinja2.PackageLoader(__name__.split('.')[0]))


async def default_validation_error_handler(request: Request, exc: ValidationError) -> Response:
    if request.wants_json:
        return JSONResponse({'message': exc.message, 'errors': exc.errors}, 400)

    await request.remember_form_data()
    request.set_form_errors(dict(exc.errors or {}))
    response = GoBackResponse(request)
    if exc.message:
        response = response.with_error(exc.message)
    return response


async def default_http_error_handler(request: Request, exc: HTTPException) -> Response:
    if request.wants_json:
        data = {'message': exc.message, 'errors': getattr(exc, 'errors', {})}
        if request.app.debug:
            exception_type = f'{exc.__class__.__module__}.{exc.__class__.__qualname__}'
            data['exception_type'] = exception_type
            data['exception'] = repr(exc)
        return JSONResponse(data, status_code=exc.status_code)
    elif request.app.debug:
        if exc.status_code in {204, 304}:
            return Response(b"", status_code=exc.status_code)
        return PlainTextResponse(exc.detail, status_code=exc.status_code)
    else:
        content = _renderer.get_template('errors/http_error.html').render({'request': request, 'exc': exc})
        return HTMLResponse(content, status_code=exc.status_code)


_default_error_handlers = {
    BaseHTTPException: default_http_error_handler,
}


class ErrorHandlers:
    def __init__(self, handlers: dict) -> None:
        self.handlers: dict = {**_default_error_handlers, **handlers}

    def get_for_exception(self, exc: Exception) -> t.Optional[ErrorHandler]:
        class_name = type(exc)
        status_code = exc.status_code if isinstance(exc, BaseHTTPException) else 0
        if status_code in self.handlers:
            return self.handlers[status_code]

        for cls in class_name.__mro__:
            if cls in self.handlers:
                return self.handlers[cls]

        return None


class ExceptionMiddleware:
    def __init__(self, app: ASGIApp, handlers: t.Dict[t.Union[int, t.Type[Exception]], ErrorHandler]) -> None:
        self.app = app
        self.handlers = ErrorHandlers(handlers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        response_started = False

        async def sender(message: Message) -> None:
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, sender)
        except Exception as exc:
            handler = self.handlers.get_for_exception(exc)
            if handler is None:
                raise exc

            if response_started:
                msg = "Caught handled exception, but response already started."
                raise RuntimeError(msg) from exc

            request = Request(scope, receive=receive)
            if inspect.iscoroutinefunction(handler):
                response = await handler(request, exc)
            else:
                response = await run_in_threadpool(handler, request, exc)
            await response(scope, receive, sender)
