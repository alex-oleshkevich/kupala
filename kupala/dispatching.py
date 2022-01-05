from dataclasses import dataclass, field

import inspect
import typing as t
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.responses import EmptyResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from kupala.templating import TemplateResponse
from kupala.utils import run_async


@dataclass
class ActionConfig:
    """Keeps endpoint configuration."""

    methods: t.List[str] = field(default_factory=list)
    template: t.Optional[str] = None
    middleware: t.Optional[t.Sequence[Middleware]] = None


def action_config(
    methods: t.List[str] = None,
    template: str = '',
    middleware: t.Sequence[Middleware] = None,
) -> t.Callable:
    """Use this decorator to configure endpoint parameters."""
    allowed_methods = methods or ['GET', 'HEAD']

    def wrapper(fn: t.Callable) -> t.Callable:
        setattr(
            fn, '__action_config__', ActionConfig(methods=allowed_methods, template=template, middleware=middleware)
        )
        return fn

    return wrapper


def get_action_config(endpoint: t.Callable) -> t.Optional[ActionConfig]:
    """Return endpoint config if defined otherwise return None."""
    return getattr(endpoint, '__action_config__', None)


def detect_request_class(endpoint: t.Callable) -> t.Type[Request]:
    """Detect which request class to use for this endpoint.
    If endpoint does not have `request` argument, or it is not type-hinted
    then default request class returned."""
    args = t.get_type_hints(endpoint)
    return args.get('request', Request)


async def resolve_injections(
    request: Request,
    endpoint: t.Callable,
    sync_stack: ExitStack,
    async_stack: AsyncExitStack,
) -> dict[str, t.Any]:
    """Read endpoint signature and extract injections types.
    These injections will be resolved into actual service instances.
    Dependency injections and path parameters are merged.

    Return value of `from_request` can be a generator. In this case we convert it into context manager
    and add to sync/async exit stack.
    """
    injections = {}

    args = t.get_type_hints(endpoint)
    for arg_name, arg_type in args.items():
        if arg_name == 'return':
            continue

        if arg_type == type(request):
            injections[arg_name] = request
            continue

        if arg_name in request.path_params:
            injections[arg_name] = request.path_params[arg_name]
            continue

        if callback := getattr(arg_type, 'from_request', None):
            if inspect.isgeneratorfunction(callback):
                injections[arg_name] = sync_stack.enter_context(contextmanager(callback)(request))
                continue

            if inspect.isasyncgenfunction(callback):
                injections[arg_name] = await async_stack.enter_async_context(asynccontextmanager(callback)(request))
                continue

            injections[arg_name] = await run_async(callback, request=request)
            continue

        injections[arg_name] = request.app.resolve(arg_type)
    return injections


def _guess_response_type(
    request: Request,
    action_config: ActionConfig | None,
    content: t.Any,
    status: int,
    headers: dict[str, str],
) -> Response:
    """When endpoint returns non-response instances, then we try to do our best to guess what response type
    we should send to the client."""
    if request.wants_json:
        return JSONResponse(content=content, status_code=status, headers=headers)

    if 'text/html' in request.headers['accept']:
        if action_config and action_config.template:
            return TemplateResponse(
                request,
                template_name=action_config.template,
                context=content,
                status_code=status,
                headers=headers,
            )
        return HTMLResponse(content, status_code=status, headers=headers)

    # default is text/plain, but we can serialize only several types
    return PlainTextResponse(str(content), status_code=status, headers=headers)


def handle_endpoint_result(request: Request, result: t.Any, action_config: ActionConfig | None) -> ASGIApp:
    """Takes return value of endpoint execution and converts it into response instance."""
    if result is None:
        return EmptyResponse()

    if isinstance(result, Response):
        return result

    if inspect.isfunction(result):  # may be request_response function aka ASGI callable
        return result

    status = 200
    headers = {}
    content = result

    if isinstance(result, tuple):
        if len(result) == 3:
            content, status, headers = result
        elif len(result) == 2:
            content, status = result

    return _guess_response_type(request, action_config, content, status, headers)


async def dispatch_endpoint(scope: Scope, receive: Receive, send: Send, endpoint: t.Callable) -> ASGIApp:
    """Call endpoint callable resolving all dependencies. Will return response."""
    request_class = detect_request_class(endpoint)
    request = request_class(scope, receive, send)
    action_config = get_action_config(endpoint)

    with ExitStack() as sync_stack:
        async with AsyncExitStack() as async_stack:
            args = await resolve_injections(request, endpoint, sync_stack, async_stack)
            if inspect.iscoroutinefunction(endpoint):
                response = await request.app.invoke(endpoint, extra_kwargs=args)
            else:
                response = await run_in_threadpool(request.app.invoke, endpoint, extra_kwargs=args)
    return handle_endpoint_result(request, response, action_config)
