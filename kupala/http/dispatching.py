from __future__ import annotations

import inspect
import typing
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.di import InjectionError
from kupala.http import guards as route_guards
from kupala.http.exceptions import PermissionDenied
from kupala.http.requests import Request
from kupala.utils import callable_name, run_async

if typing.TYPE_CHECKING:
    from kupala.http.middleware import Middleware


def route(
    methods: list[str] = None,
    middleware: typing.Sequence[Middleware] = None,
    guards: list[route_guards.Guard] | None = None,
    is_authenticated: bool = False,
    permission: str | None = None,
) -> typing.Callable:
    """Use this decorator to configure endpoint parameters."""
    allowed_methods = methods or ['GET', 'HEAD']

    guards = guards or []
    if is_authenticated:
        guards.append(route_guards.is_authenticated)

    if permission:
        guards.append(route_guards.has_permission(permission))

    def wrapper(fn: typing.Callable) -> typing.Callable:
        setattr(fn, '__route_methods__', allowed_methods)
        setattr(fn, '__route_guards__', guards)
        setattr(fn, '__route_middleware__', middleware)
        return fn

    return wrapper


def detect_request_class(endpoint: typing.Callable) -> typing.Type[Request]:
    """
    Detect which request class to use for this endpoint.

    If endpoint does not have `request` argument, or it is not type-hinted then
    default request class returned.
    """
    args = typing.get_type_hints(endpoint)
    return args.get('request', Request)


async def call_guards(request: Request, guards: typing.Iterable[route_guards.Guard]) -> None:
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
    endpoint: typing.Callable,
    sync_stack: ExitStack,
    async_stack: AsyncExitStack,
) -> dict[str, typing.Any]:
    """
    Read endpoint signature and extract injections types. These injections will
    be resolved into actual service instances. Dependency injections and path
    parameters are merged.

    Return value of `from_request` can be a generator. In this case we convert
    it into context manager and add to sync/async exit stack.
    """
    injections = {}

    args = typing.get_type_hints(endpoint)
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

        # handle request injectable arguments
        if request.app.dependencies.has(arg_type, 'request'):
            callback = request.app.dependencies.get(arg_type, 'request')
            if inspect.isgeneratorfunction(callback):
                injections[arg_name] = sync_stack.enter_context(contextmanager(callback)(request))
                continue

            if inspect.isasyncgenfunction(callback):
                injections[arg_name] = await async_stack.enter_async_context(asynccontextmanager(callback)(request))
                continue

            # not a generator?
            injections[arg_name] = await run_async(callback, request)
            continue

        # all other endpoint arguments are must be considered as injections
        try:
            injection = request.app.dependencies.get(arg_type)
            injections[arg_name] = await injection if inspect.iscoroutine(injection) else injection
        except InjectionError as ex:
            if arg_name in signature.parameters and signature.parameters[arg_name].default != signature.empty:
                injections[arg_name] = signature.parameters[arg_name].default
            else:
                raise InjectionError(
                    f'Injection "{arg_name}" cannot be processed in {callable_name(endpoint)}. ' f'Error: {ex}.'
                ) from ex
        else:
            continue

    return injections


async def dispatch_endpoint(scope: Scope, receive: Receive, send: Send, endpoint: typing.Callable) -> ASGIApp:
    """
    Call endpoint callable resolving all dependencies.

    Will return response.
    """
    request_class = detect_request_class(endpoint)
    request = request_class(scope, receive, send)
    await call_guards(request, getattr(endpoint, '__route_guards__', []))

    with ExitStack() as sync_stack:
        async with AsyncExitStack() as async_stack:
            args = await resolve_injections(request, endpoint, sync_stack, async_stack)
            if inspect.iscoroutinefunction(endpoint):
                response = await endpoint(**args)
            else:
                response = await run_in_threadpool(endpoint, **args)
    return response
