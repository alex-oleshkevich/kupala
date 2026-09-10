from __future__ import annotations

import dataclasses
import functools
import inspect
import typing

from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.routing import BaseRoute, Host, Mount, Route, WebSocketRoute
from starlette.types import ASGIApp

from kupala import inspection
from kupala.binders import ModelBinder
from kupala.dependencies import (
    INVOCATION_CONTEXT_KEY,
    CallableInfo,
    CallPlan,
    CompileContext,
    InvocationContext,
    UnsupportedParameterError,
    compile_call_plan,
    constant,
    inspect_callable,
    invoke,
    resolve_arguments,
)
from kupala.middleware import (
    CallNext,
    Middleware,
    WebSocketCallNext,
    WebSocketMiddleware,
)
from kupala.requests import Request
from kupala.responses import Response
from kupala.schema import openapi
from kupala.schema.openapi import Operation
from kupala.websockets import WebSocket

# the request and the continuation, which every middleware takes before its dependencies
MIDDLEWARE_ARGUMENTS = 2

# endpoints receive their arguments from the dependency injector, so any signature is valid
type SyncEndpoint = typing.Callable[..., Response]
type AnyEndpoint = typing.Callable[..., Response | typing.Awaitable[Response]]
type AnyResponse = Response | typing.Awaitable[Response]
type AsyncEndpoint = typing.Callable[..., typing.Awaitable[Response]]
type EndpointWrapper = typing.Callable[[AnyEndpoint], AnyEndpoint]
type WebSocketEndpoint = typing.Callable[..., typing.Awaitable[None]]
type WebSocketEndpointWrapper = typing.Callable[[WebSocketEndpoint], WebSocketEndpoint]

OperationOptions = openapi.Operation


def split_docstring(docstring: str | None) -> tuple[str | None, str | None]:
    """Read a docstring as an operation summary and description, the way the specification pairs them.

    The first paragraph is the summary, joined onto one line because that is what a summary is, and
    everything after it is the description.
    """

    if not docstring:
        return None, None

    summary, _, description = inspect.cleandoc(docstring).partition("\n\n")
    return summary.replace("\n", " "), description.strip() or None


@dataclasses.dataclass
class RouteDefinition:
    path: str
    fn: AnyEndpoint
    name: str | None
    methods: tuple[str, ...]
    middleware: tuple[Middleware, ...]
    openapi: Operation | None = None

    @functools.cached_property
    def call(self) -> CallableInfo[..., typing.Any]:
        """The endpoint's signature, for tools that describe what it accepts and returns.

        Derived from the endpoint alone, so it needs no binders and no compiled application.
        """

        return inspect_callable(self.fn)


@dataclasses.dataclass
class WebSocketDefinition:
    path: str
    name: str | None
    fn: WebSocketEndpoint
    middleware: tuple[WebSocketMiddleware, ...]


@dataclasses.dataclass
class MountDefinition:
    path: str
    name: str | None
    app: ASGIApp
    asgi_middleware: tuple[ASGIMiddlewareWrapper, ...]


@dataclasses.dataclass
class HostDefinition:
    host: str
    name: str | None
    app: ASGIApp
    asgi_middleware: tuple[ASGIMiddlewareWrapper, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class RouteInfo:
    """Where one route ended up in the tree, which is the part its definition cannot know.

    A definition may sit under two parents at once, so a resolved `path` and `name` belong here rather
    than on it. Everything a route carries regardless of position — its methods, its operation, its
    endpoint's signature — stays on `definition`.
    """

    path: str
    name: str
    definition: RouteDefinition


class RouteConflictError(ValueError):
    """Raised when route definitions create an ambiguous application."""


class Routes:
    def __init__(
        self,
        *,
        prefix: str = "",
        middleware: typing.Sequence[Middleware] = (),
        websocket_middleware: typing.Sequence[WebSocketMiddleware] = (),
        namespace: str = "",
        tags: typing.Sequence[str] = (),
        children: typing.Sequence[Routes] = (),
    ) -> None:
        self.prefix = prefix
        self.namespace = namespace
        self.middleware = list(middleware)
        self.tags = list(tags)
        self.websocket_middleware = list(websocket_middleware)

        self.definitions: list[RouteDefinition | WebSocketDefinition | MountDefinition | HostDefinition] = []
        self._children: list[Routes] = list(children)

    def include(self, routes: Routes) -> None:
        self._children.append(routes)

    def group(
        self,
        prefix: str = "",
        *,
        namespace: str = "",
        middleware: typing.Sequence[Middleware] = (),
        websocket_middleware: typing.Sequence[WebSocketMiddleware] = (),
        tags: typing.Sequence[str] = (),
    ) -> typing.Self:
        child = self.__class__(
            middleware=middleware,
            websocket_middleware=websocket_middleware,
            prefix=prefix,
            namespace=namespace,
            tags=(*self.tags, *tags),
        )
        self.include(child)
        return child

    def operation(self, fn: AnyEndpoint, options: OperationOptions) -> openapi.Operation:
        """Describe one endpoint, deriving what the group and the docstring know and keeping the rest."""

        summary, description = split_docstring(fn.__doc__)
        return dataclasses.replace(
            options,
            tags=(*self.tags, *(options.tags or ())) or None,
            summary=options.summary or summary,
            description=options.description or description,
            deprecated=options.deprecated or None,
        )

    def _wrap(
        self,
        path: str,
        *,
        methods: typing.Sequence[str],
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        include_in_schema = options.pop("include_in_schema", True)
        settings = OperationOptions(**options)

        def decorator(fn: AnyEndpoint) -> AnyEndpoint:
            self.add(
                path=path,
                methods=tuple(methods),
                name=name,
                middleware=tuple(middleware),
                fn=fn,
                openapi=self.operation(fn, settings) if include_in_schema else None,
            )
            return fn

        return decorator

    def add(
        self,
        path: str,
        fn: AnyEndpoint,
        *,
        methods: typing.Sequence[str],
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        openapi: Operation | None = None,
    ) -> None:
        self.definitions.append(
            RouteDefinition(
                path=path,
                methods=tuple(methods),
                name=name,
                middleware=tuple(middleware),
                fn=fn,
                openapi=openapi,
            )
        )

    def get(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        return self._wrap(path, name=name, methods=["GET", "HEAD"], middleware=middleware, **options)

    def post(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["POST"], middleware=middleware, **options)

    def get_or_post(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["GET", "HEAD", "POST"], middleware=middleware, **options)

    def put(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["PUT"], middleware=middleware, **options)

    def patch(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["PATCH"], middleware=middleware, **options)

    def delete(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["DELETE"], middleware=middleware, **options)

    def head(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        **options: typing.Any,
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["HEAD"], middleware=middleware, **options)

    def mount(
        self,
        path: str,
        app: ASGIApp,
        *,
        name: str | None = None,
        asgi_middleware: typing.Sequence[ASGIMiddlewareWrapper] = (),
    ) -> None:
        self.definitions.append(
            MountDefinition(
                name=name,
                path=path,
                app=app,
                asgi_middleware=tuple(asgi_middleware),
            )
        )

    def host(
        self,
        host: str,
        app: ASGIApp,
        *,
        name: str | None = None,
        asgi_middleware: typing.Sequence[ASGIMiddlewareWrapper] = (),
    ) -> None:
        self.definitions.append(
            HostDefinition(
                app=app,
                name=name,
                host=host,
                asgi_middleware=tuple(asgi_middleware),
            )
        )

    def websocket(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[WebSocketMiddleware] = (),
    ) -> WebSocketEndpointWrapper:
        def decorator(fn: WebSocketEndpoint) -> WebSocketEndpoint:
            self.definitions.append(
                WebSocketDefinition(
                    fn=fn,
                    name=name,
                    path=path,
                    middleware=tuple(middleware),
                )
            )
            return fn

        return decorator

    def describe(self) -> typing.Iterator[RouteInfo]:
        """Yield every HTTP route this tree declares, with its path and name already resolved.

        Nothing here compiles, binds or resolves, so a tool may call it before the application is built
        and as often as it likes. Mounts and hosts are absent because they dispatch to another
        application, which describes itself or does not; WebSocket routes have no shape in common with
        an HTTP one, so they are absent too.
        """

        return self._describe("", "")

    def _describe(self, parent_prefix: str, parent_namespace: str) -> typing.Iterator[RouteInfo]:
        prefix = join_path(parent_prefix, self.prefix)
        namespace = join_namespace(parent_namespace, self.namespace)

        for definition in self.definitions:
            if isinstance(definition, RouteDefinition):
                path, name = resolve_route(definition, prefix, namespace)
                yield RouteInfo(path=path, name=name, definition=definition)

        for child in self._children:
            yield from child._describe(prefix, namespace)

    def compile(
        self,
        http_middleware: tuple[Middleware, ...],
        websocket_middleware: tuple[WebSocketMiddleware, ...] = (),
        binders: tuple[ModelBinder, ...] = (),
    ) -> list[BaseRoute]:
        route_names: dict[str, str] = {}
        http_routes: dict[tuple[str, str], str] = {}

        def register_name(name: str, description: str) -> None:
            if not name:
                return

            previous = route_names.get(name)
            if previous is not None:
                raise RouteConflictError(f"Duplicate route name {name!r}: {description} conflicts with {previous}.")
            route_names[name] = description

        def register_http_route(path: str, methods: tuple[str, ...], name: str) -> None:
            for method in dict.fromkeys(methods):
                key = (path, method)
                previous = http_routes.get(key)
                if previous is not None:
                    raise RouteConflictError(
                        f"Duplicate HTTP route {method} {path!r}: {name!r} conflicts with {previous!r}."
                    )
                http_routes[key] = name

        def _visit(
            group: Routes,
            parent_prefix: str,
            parent_namespace: str,
            parent_middleware: tuple[Middleware, ...],
            parent_websocket_middleware: tuple[WebSocketMiddleware, ...],
        ) -> list[BaseRoute]:
            compiled: list[BaseRoute] = []
            prefix = join_path(parent_prefix, group.prefix)
            namespace = join_namespace(parent_namespace, group.namespace)
            middleware = (*parent_middleware, *group.middleware)
            group_websocket_middleware = (*parent_websocket_middleware, *group.websocket_middleware)

            for definition in group.definitions:
                match definition:
                    case MountDefinition():
                        route_name = join_namespace(namespace, definition.name or "")
                        register_name(route_name, f"mount {definition.path!r}")
                        compiled.append(
                            Mount(
                                app=definition.app,
                                middleware=definition.asgi_middleware,
                                path=join_path(prefix, definition.path),
                                name=route_name,
                            )
                        )
                    case HostDefinition():
                        route_name = join_namespace(namespace, definition.name or "")
                        register_name(route_name, f"host {definition.host!r}")
                        host_app = definition.app
                        for cls, args, kwargs in reversed(definition.asgi_middleware):
                            host_app = cls(host_app, *args, **kwargs)

                        compiled.append(
                            Host(
                                host=definition.host,
                                app=host_app,
                                name=route_name,
                            )
                        )

                    case WebSocketDefinition():
                        route_path, route_name = resolve_route(definition, prefix, namespace)
                        register_name(route_name, f"WebSocket route {route_path!r}")
                        compiled.append(
                            WebSocketRoute(
                                path=route_path,
                                name=route_name,
                                endpoint=chain_websocket_middleware(
                                    bind_websocket_dependencies(definition.fn, binders),
                                    [*websocket_middleware, *group_websocket_middleware, *definition.middleware],
                                    binders,
                                ),
                            )
                        )

                    case RouteDefinition():
                        route_path, route_name = resolve_route(definition, prefix, namespace)
                        register_name(route_name, f"HTTP route {route_path!r}")
                        register_http_route(route_path, definition.methods, route_name)
                        compiled.append(
                            Route(
                                path=route_path,
                                name=route_name,
                                methods=definition.methods,
                                endpoint=chain_middleware(
                                    bind_http_dependencies(definition.fn, binders),
                                    [*http_middleware, *middleware, *definition.middleware],
                                    binders,
                                ),
                            )
                        )

                    case _:  # pragma: no cover - every definition type is handled above
                        raise AssertionError(f"Unhandled route definition: {type(definition).__name__}.")

            for child in group._children:
                compiled.extend(
                    _visit(
                        child,
                        prefix,
                        namespace,
                        middleware,
                        group_websocket_middleware,
                    )
                )

            return compiled

        return _visit(self, "", "", (), ())

    def __len__(self) -> int:
        return len(self.definitions)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({len(self.definitions)} definitions)"

    def __iter__(self) -> typing.Iterator[RouteDefinition | WebSocketDefinition | MountDefinition | HostDefinition]:
        return iter(self.definitions)


def join_path(parent: str, child: str) -> str:
    parent = parent.rstrip("/")
    child = child.lstrip("/")

    if not child:
        return parent or "/"

    result = f"{parent}/{child}"
    if child.endswith("/") and result != "/":
        return result.rstrip("/") + "/"
    return result


def resolve_route(
    definition: RouteDefinition | WebSocketDefinition,
    prefix: str,
    namespace: str,
) -> tuple[str, str]:
    """One route's path and name as they will be served, resolved against the group enclosing it.

    Route paths and names are public behaviour, so this is the single place that decides them: both
    `compile` and `describe` read it, and an unnamed route falls back to its endpoint either way.
    """

    return (
        join_path(prefix, definition.path),
        join_namespace(namespace, definition.name or endpoint_name(definition.fn)),
    )


def endpoint_name(fn: AnyEndpoint | WebSocketEndpoint) -> str:
    # callable objects have no `__name__`, so fall back to their class name
    name: str = getattr(fn, "__name__", type(fn).__name__)
    return name


def join_namespace(parent: str, child: str, separator: str = ".") -> str:
    if parent and child:
        return f"{parent}{separator}{child}"
    return parent or child


def chain_middleware(
    endpoint: AsyncEndpoint,
    middleware: typing.Sequence[Middleware],
    binders: tuple[ModelBinder, ...] = (),
) -> AsyncEndpoint:
    async def call_endpoint(request: Request) -> Response:
        return await endpoint(request)

    call_next: CallNext = call_endpoint
    for current in reversed(middleware):
        call_next = bind_middleware(current, call_next, binders)

    return call_next


def middleware_dependencies[**PS, R](plan: CallPlan[PS, R]) -> CallPlan[PS, R]:
    """Drop the two arguments the framework passes itself, leaving what the injector must resolve.

    The signature `Middleware` declares fixes the first two, so they need no binding and no lookup;
    everything after them is an ordinary dependency.
    """

    owner = inspection.callable_name(plan.callable.callable)
    if len(plan.parameters) < MIDDLEWARE_ARGUMENTS:
        raise UnsupportedParameterError(
            f"Middleware {owner}() must accept the request and the continuation before anything "
            f"it depends on, as `async def {plan.callable.callable.__name__}(request, call_next, /, ...)`."
        )

    dependencies = plan.parameters[MIDDLEWARE_ARGUMENTS:]
    positional = [entry.param.name for entry in dependencies if entry.param.kind is inspect.Parameter.POSITIONAL_ONLY]
    if positional:
        listed = ", ".join(repr(name) for name in positional)
        raise UnsupportedParameterError(
            f"Middleware {owner}() marks {listed} positional-only, but the injector passes "
            f"dependencies by keyword. Move the `/` so only the request and the continuation precede it."
        )

    return dataclasses.replace(plan, parameters=dependencies)


def bind_middleware(
    middleware: Middleware,
    call_next: CallNext,
    binders: tuple[ModelBinder, ...],
) -> CallNext:
    """Compile one middleware, resolving everything it declares after the fixed two."""

    plan = middleware_dependencies(compile_call_plan(middleware, CompileContext(binders=binders)))

    async def wrapped(request: Request) -> Response:
        # a child so a dependency that reads the request sees the one this link was handed - a
        # middleware above may have passed a different one down - while the cache and the exit
        # stack stay the invocation's own, and one session serves the whole chain
        root: InvocationContext = request.scope[INVOCATION_CONTEXT_KEY]
        arguments = await resolve_arguments(plan, root.child({Request: constant(request)}))
        return await middleware(request, call_next, **arguments)

    return wrapped


def chain_websocket_middleware(
    endpoint: WebSocketEndpoint,
    middleware: typing.Sequence[WebSocketMiddleware],
    binders: tuple[ModelBinder, ...] = (),
) -> WebSocketEndpoint:
    async def call_endpoint(ws: WebSocket) -> None:
        return await endpoint(ws)

    call_next: WebSocketCallNext = call_endpoint
    for current in reversed(middleware):
        call_next = bind_websocket_middleware(current, call_next, binders)

    return call_next


def bind_websocket_middleware(
    middleware: WebSocketMiddleware,
    call_next: WebSocketCallNext,
    binders: tuple[ModelBinder, ...],
) -> WebSocketCallNext:
    """Compile one WebSocket middleware, the way `bind_middleware` compiles an HTTP one."""

    plan = middleware_dependencies(compile_call_plan(middleware, CompileContext(binders=binders)))

    async def wrapped(ws: WebSocket) -> None:
        root: InvocationContext = ws.scope[INVOCATION_CONTEXT_KEY]
        arguments = await resolve_arguments(plan, root.child({WebSocket: constant(ws)}))
        await middleware(ws, call_next, **arguments)

    return wrapped


def bind_http_dependencies(fn: AnyEndpoint, binders: tuple[ModelBinder, ...]) -> AsyncEndpoint:
    plan = compile_call_plan(fn, CompileContext(binders=binders))

    async def wrapped(request: Request) -> Response:
        # the request a middleware passed down, not the one the route was matched with
        root: InvocationContext = request.scope[INVOCATION_CONTEXT_KEY]
        return await invoke(plan, root.child({Request: constant(request)}))

    return wrapped


def bind_websocket_dependencies(fn: WebSocketEndpoint, binders: tuple[ModelBinder, ...]) -> WebSocketEndpoint:
    plan = compile_call_plan(fn, CompileContext(binders=binders))

    async def wrapped(ws: WebSocket) -> None:
        root: InvocationContext = ws.scope[INVOCATION_CONTEXT_KEY]
        await invoke(plan, root.child({WebSocket: constant(ws)}))

    return wrapped
