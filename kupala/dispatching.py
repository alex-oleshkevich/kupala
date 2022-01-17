from dataclasses import dataclass, field

import inspect
import typing
import typing as t
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.di import InjectionError, get_request_injection_factory
from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.responses import EmptyResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from kupala.templating import TemplateResponse
from kupala.utils import run_async


def _callable_name(injection: typing.Any) -> str:
    class_name = injection.__name__ if inspect.isclass(injection) else getattr(injection, '__name__', repr(injection))
    module_name = getattr(injection, '__module__', '')
    return f'{module_name}.{class_name}{inspect.signature(injection)}'


ViewDispatchResult = typing.Union[
    typing.Callable[[Scope, Receive, Send], ASGIApp],
    Response,
    typing.Any,
    typing.Union[typing.Any, int],
    typing.Union[typing.Any, int, typing.Mapping],
]


@dataclass
class ActionConfig:
    """Keeps endpoint configuration."""

    methods: t.List[str] = field(default_factory=list)
    renderer: str = ''
    middleware: t.Optional[t.Sequence[Middleware]] = None


def action_config(
    methods: t.List[str] = None,
    renderer: str = '',
    middleware: t.Sequence[Middleware] = None,
) -> t.Callable:
    """Use this decorator to configure endpoint parameters."""
    allowed_methods = methods or ['GET', 'HEAD']

    def wrapper(fn: t.Callable) -> t.Callable:
        action_config = ActionConfig(methods=allowed_methods, renderer=renderer, middleware=middleware)
        setattr(fn, '__action_config__', action_config)
        return fn

    return wrapper


def get_action_config(endpoint: t.Callable) -> ActionConfig:
    """Return endpoint config if defined otherwise return None."""
    if not hasattr(endpoint, '__action_config__'):
        endpoint.__dict__['__action_config__'] = ActionConfig()
    return getattr(endpoint, '__action_config__')


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
    signature = inspect.signature(endpoint)
    for arg_name, arg_type in args.items():
        if arg_name == 'return':
            continue

        if arg_type == type(request):
            injections[arg_name] = request
            continue

        if arg_name in request.path_params:
            injections[arg_name] = request.path_params[arg_name]
            continue

        if callback := get_request_injection_factory(arg_type):
            if inspect.isgeneratorfunction(callback):
                injections[arg_name] = sync_stack.enter_context(contextmanager(callback)(request))
                continue

            if inspect.isasyncgenfunction(callback):
                injections[arg_name] = await async_stack.enter_async_context(asynccontextmanager(callback)(request))
                continue

            injections[arg_name] = await run_async(callback, request)
            continue

        try:
            injection = request.app.di.make(arg_type)
            if inspect.iscoroutine(injection):
                injection = await injection
            injections[arg_name] = injection
        except InjectionError as ex:
            if arg_name in signature.parameters and signature.parameters[arg_name].default != signature.empty:
                injections[arg_name] = signature.parameters[arg_name].default
            else:
                raise InjectionError(
                    f'Injection "{arg_name}" cannot be processed in {_callable_name(endpoint)}.'
                ) from ex
        else:
            continue

    return injections


async def dispatch_endpoint(scope: Scope, receive: Receive, send: Send, endpoint: t.Callable) -> ASGIApp:
    """Call endpoint callable resolving all dependencies. Will return response."""
    request_class = detect_request_class(endpoint)
    request = request_class(scope, receive, send)
    action_config = get_action_config(endpoint)

    with ExitStack() as sync_stack:
        async with AsyncExitStack() as async_stack:
            args = await resolve_injections(request, endpoint, sync_stack, async_stack)
            if inspect.iscoroutinefunction(endpoint):
                response = await endpoint(**args)
            else:
                response = await run_in_threadpool(endpoint, **args)
    return request.app.view_renderer.render(request, action_config, response)


class ViewResult(typing.TypedDict):
    content: typing.Any
    status_code: int
    headers: dict[str, typing.Any]


class ViewRenderer(typing.Protocol):  # pragma: nocover
    def __call__(self, request: Request, action_config: ActionConfig, view_result: ViewResult) -> Response:
        ...


def plain_text_view_renderer(request: Request, action_config: ActionConfig, view_result: ViewResult) -> Response:
    return PlainTextResponse(
        str(view_result['content']),
        status_code=view_result['status_code'],
        headers=view_result['headers'],
    )


def html_view_renderer(request: Request, action_config: ActionConfig, view_result: ViewResult) -> Response:
    return HTMLResponse(
        str(view_result['content']),
        status_code=view_result['status_code'],
        headers=view_result['headers'],
    )


def json_view_renderer(request: Request, action_config: ActionConfig, view_result: ViewResult) -> Response:
    return JSONResponse(
        view_result['content'],
        status_code=view_result['status_code'],
        headers=view_result['headers'],
    )


def template_view_renderer(request: Request, action_config: ActionConfig, view_result: ViewResult) -> Response:
    return TemplateResponse(
        request=request,
        template_name=action_config.renderer,
        context=view_result['content'],
        status_code=view_result['status_code'],
        headers=view_result['headers'],
    )


class ViewResultRenderer:
    def __init__(self) -> None:
        self._renderers: dict[str, ViewRenderer] = {}
        self.add_renderer('text', plain_text_view_renderer)
        self.add_renderer('html', html_view_renderer)
        self.add_renderer('json', json_view_renderer)

    def add_renderer(self, name: str, renderer: ViewRenderer) -> None:
        self._renderers[name] = renderer

    def find_renderer(self, renderer_name: str) -> ViewRenderer:
        assert renderer_name in self._renderers, f'No view result renderer named "{renderer_name}" registered.'
        return self._renderers[renderer_name]

    def render(self, request: Request, action_config: ActionConfig, view_result: ViewDispatchResult | None) -> ASGIApp:
        if view_result is None:
            return EmptyResponse()

        if isinstance(view_result, Response):
            return view_result

        if inspect.isfunction(view_result):  # may be request_response function aka ASGI callable
            return view_result

        status = 200
        headers = {}
        content = view_result

        if isinstance(view_result, tuple):
            if len(view_result) == 3:
                content, status, headers = view_result
            elif len(view_result) == 2:
                content, status = view_result

        # if renderer has a dot (file extension separator) then force template renderer
        if '.' in action_config.renderer:
            renderer = template_view_renderer
        else:
            renderer = self.find_renderer(action_config.renderer)
        return renderer(request, action_config, {'content': content, 'status_code': status, 'headers': headers})
