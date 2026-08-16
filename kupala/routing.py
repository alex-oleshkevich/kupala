from __future__ import annotations

import dataclasses
import functools
import inspect
import typing

from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware as ASGIMiddlewareWrapper
from starlette.routing import BaseRoute, Host, Mount, Route, WebSocketRoute
from starlette.types import ASGIApp

from kupala.dependencies import DependencyResolver
from kupala.middleware import (
    CallNext,
    Middleware,
    WebSocketCallNext,
    WebSocketMiddleware,
)
from kupala.requests import Request
from kupala.responses import Response
from kupala.websockets import WebSocket

type SyncEndpoint = typing.Callable[[Request], Response]
type AnyEndpoint = typing.Callable[[Request], Response | typing.Awaitable[Response]]
type AnyResponse = Response | typing.Awaitable[Response]
type AsyncEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
type EndpointWrapper = typing.Callable[[AnyEndpoint], AnyEndpoint]
type WebSocketEndpoint = typing.Callable[[WebSocket], typing.Awaitable[None]]
type WebSocketEndpointWrapper = typing.Callable[[WebSocketEndpoint], WebSocketEndpoint]


@dataclasses.dataclass
class RouteDefinition:
    path: str
    fn: AnyEndpoint
    name: str | None
    methods: tuple[str, ...]
    middleware: tuple[Middleware, ...]


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


class Routes:
    def __init__(
        self,
        *,
        prefix: str = "",
        middleware: typing.Sequence[Middleware] = (),
        websocket_middleware: typing.Sequence[WebSocketMiddleware] = (),
        namespace: str = "",
        children: typing.Sequence[Routes] = (),
    ) -> None:
        self.prefix = prefix
        self.namespace = namespace
        self.middleware = list(middleware)
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
    ) -> typing.Self:
        child = self.__class__(
            middleware=middleware,
            websocket_middleware=websocket_middleware,
            prefix=prefix,
            namespace=namespace,
        )
        self.include(child)
        return child

    def _wrap(
        self,
        path: str,
        *,
        methods: typing.Sequence[str],
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        def decorator(fn: AnyEndpoint) -> AnyEndpoint:
            self.definitions.append(
                RouteDefinition(path=path, methods=tuple(methods), name=name, middleware=tuple(middleware), fn=fn)
            )
            return fn

        return decorator

    def get(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        return self._wrap(path, name=name, methods=["GET", "HEAD"], middleware=middleware)

    def post(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["POST"], middleware=middleware)

    def get_or_post(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["GET", "HEAD", "POST"], middleware=middleware)

    def put(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["PUT"], middleware=middleware)

    def patch(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["PATCH"], middleware=middleware)

    def delete(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["DELETE"], middleware=middleware)

    def head(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
    ) -> EndpointWrapper:
        return self._wrap(path=path, name=name, methods=["HEAD"], middleware=middleware)

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

    def compile(
        self,
        binder: DependencyResolver,
        http_middleware: tuple[Middleware, ...],
        websocket_middleware: tuple[WebSocketMiddleware, ...] = (),
    ) -> list[BaseRoute]:
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
                        compiled.append(
                            Mount(
                                app=definition.app,
                                middleware=definition.asgi_middleware,
                                path=join_path(prefix, definition.path),
                                name=join_namespace(namespace, definition.name or ""),
                            )
                        )
                    case HostDefinition():
                        host_app = definition.app
                        for cls, args, kwargs in reversed(definition.asgi_middleware):
                            host_app = cls(host_app, *args, **kwargs)

                        compiled.append(
                            Host(
                                host=definition.host,
                                app=host_app,
                                name=join_namespace(namespace, definition.name or ""),
                            )
                        )

                    case WebSocketDefinition():
                        route_name = join_namespace(namespace, definition.name or definition.fn.__name__)
                        route_path = join_path(prefix, definition.path)
                        compiled.append(
                            WebSocketRoute(
                                path=route_path,
                                name=route_name,
                                endpoint=chain_websocket_middleware(
                                    definition.fn,
                                    [*websocket_middleware, *group_websocket_middleware, *definition.middleware],
                                ),
                            )
                        )

                    case RouteDefinition():
                        route_name = join_namespace(namespace, definition.name or definition.fn.__name__)
                        route_path = join_path(prefix, definition.path)
                        middleware = (*parent_middleware, *group.middleware)
                        compiled.append(
                            Route(
                                path=route_path,
                                name=route_name,
                                methods=definition.methods,
                                endpoint=chain_middleware(
                                    definition.fn,
                                    [*http_middleware, *middleware, *definition.middleware],
                                ),
                            )
                        )

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


def join_namespace(parent: str, child: str, separator: str = ".") -> str:
    if parent and child:
        return f"{parent}{separator}{child}"
    return parent or child


def chain_middleware(
    endpoint: AnyEndpoint,
    middleware: typing.Sequence[Middleware],
) -> AsyncEndpoint:
    async def call_next(request: Request) -> Response:
        return await invoke_endpoint(request, endpoint)

    async def middleware_wrapper(request: Request, call_next: CallNext, mw: Middleware) -> Response:
        return await mw(request, call_next)

    for m in reversed(middleware):
        call_next = functools.partial(middleware_wrapper, call_next=call_next, mw=m)

    return call_next


def chain_websocket_middleware(
    endpoint: WebSocketEndpoint,
    middleware: typing.Sequence[WebSocketMiddleware],
) -> WebSocketEndpoint:
    async def call_endpoint(ws: WebSocket) -> None:
        return await endpoint(ws)

    call_next: WebSocketCallNext = call_endpoint
    for current in reversed(middleware):
        previous = call_next

        async def wrapped(
            ws: WebSocket,
            *,
            current: WebSocketMiddleware = current,
            previous: WebSocketCallNext = previous,
        ) -> None:
            await current(ws, previous)

        call_next = wrapped

    return call_next


def is_async_endpoint(fn: AnyEndpoint) -> typing.TypeGuard[AsyncEndpoint]:
    return inspect.iscoroutinefunction(fn)


def is_sync_endpoint(fn: AnyEndpoint) -> typing.TypeGuard[SyncEndpoint]:
    return not inspect.iscoroutinefunction(fn)


async def invoke_endpoint(request: Request, endpoint: AnyEndpoint) -> Response:
    if is_async_endpoint(endpoint):
        return await endpoint(request)

    if is_sync_endpoint(endpoint):
        return await run_in_threadpool(endpoint, request)

    raise AssertionError("Unsupported endpoint")
