from dataclasses import dataclass, field

import inspect
import typing
import typing as t
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala import guards as route_guards
from kupala.di import InjectionError, get_request_injection_factory
from kupala.exceptions import PermissionDenied
from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.utils import run_async


def _callable_name(injection: typing.Any) -> str:
    class_name = injection.__name__ if inspect.isclass(injection) else getattr(injection, '__name__', repr(injection))
    module_name = getattr(injection, '__module__', '')
    return f'{module_name}.{class_name}{inspect.signature(injection)}'


@dataclass
class ActionConfig:
    """Keeps endpoint configuration."""

    methods: t.List[str] = field(default_factory=list)
    middleware: t.Optional[t.Sequence[Middleware]] = None
    guards: list[route_guards.Guard] | None = None


def route(
    methods: t.List[str] = None,
    middleware: t.Sequence[Middleware] = None,
    guards: list[route_guards.Guard] | None = None,
    is_authenticated: bool = False,
    permission: str | None = None,
) -> t.Callable:
    """Use this decorator to configure endpoint parameters."""
    allowed_methods = methods or ['GET', 'HEAD']

    guards = guards or []
    if is_authenticated:
        guards.append(route_guards.is_authenticated)

    if permission:
        guards.append(route_guards.has_permission(permission))

    def wrapper(fn: t.Callable) -> t.Callable:
        action_config = ActionConfig(
            methods=allowed_methods,
            middleware=middleware,
            guards=guards,
        )
        setattr(fn, '__action_config__', action_config)
        return fn

    return wrapper


action_config = route


def get_action_config(endpoint: t.Callable) -> ActionConfig:
    """Return endpoint config if defined otherwise return None."""
    if not hasattr(endpoint, '__action_config__'):
        endpoint.__dict__['__action_config__'] = ActionConfig()
    return getattr(endpoint, '__action_config__')


def detect_request_class(endpoint: t.Callable) -> t.Type[Request]:
    """
    Detect which request class to use for this endpoint.

    If endpoint does not have `request` argument, or it is not type-hinted then
    default request class returned.
    """
    args = t.get_type_hints(endpoint)
    return args.get('request', Request)


async def call_guards(request: Request, guards: t.Iterable[route_guards.Guard]) -> None:
    """Call route guards."""
    for guard in guards:
        if inspect.iscoroutinefunction(guard):
            result = guard(request)
        else:
            result = await run_in_threadpool(guard, request)

        if inspect.iscoroutine(result):
            result = await result

        if result is False:
            raise PermissionDenied('You are not allowed to access this page.')


async def resolve_injections(
    request: Request,
    endpoint: t.Callable,
    sync_stack: ExitStack,
    async_stack: AsyncExitStack,
) -> dict[str, t.Any]:
    """
    Read endpoint signature and extract injections types. These injections will
    be resolved into actual service instances. Dependency injections and path
    parameters are merged.

    Return value of `from_request` can be a generator. In this case we convert
    it into context manager and add to sync/async exit stack.
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
    """
    Call endpoint callable resolving all dependencies.

    Will return response.
    """
    request_class = detect_request_class(endpoint)
    request = request_class(scope, receive, send)
    action_config = get_action_config(endpoint)
    await call_guards(request, action_config.guards or [])

    with ExitStack() as sync_stack:
        async with AsyncExitStack() as async_stack:
            args = await resolve_injections(request, endpoint, sync_stack, async_stack)
            if inspect.iscoroutinefunction(endpoint):
                response = await endpoint(**args)
            else:
                response = await run_in_threadpool(endpoint, **args)
    return response
