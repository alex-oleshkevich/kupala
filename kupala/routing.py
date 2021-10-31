from __future__ import annotations

import functools
import inspect
import typing
import typing as t
from os import PathLike
from starlette import routing
from starlette.routing import Mount, WebSocketRoute, compile_path, get_name, request_response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.resources import Resource
from kupala.responses import RedirectResponse, Response


def apply_middleware(app: t.Callable, middleware: t.Sequence[Middleware]) -> ASGIApp:
    for mw in reversed(middleware):
        app = mw.wrap(app)
    return app


class Router(routing.Router):
    pass


class Route(routing.Route):
    def __init__(
        self,
        path: str,
        endpoint: typing.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        methods: typing.List[str] = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        assert path.startswith("/"), "Routed paths must start with '/'"
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.include_in_schema = include_in_schema

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func
        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            # Endpoint is function or method. Treat it as `func(request) -> response`.
            self.app = request_response(endpoint)
            if methods is None:
                methods = ["GET"]
        else:
            # Endpoint is a class. Treat it as ASGI.
            self.app = endpoint

        if middleware is not None:
            self.app = apply_middleware(t.cast(t.Callable, self.app), middleware)

        if methods is None:
            self.methods = None
        else:
            self.methods = {method.upper() for method in methods}
            if "GET" in self.methods:
                self.methods.add("HEAD")

        self.path_regex, self.path_format, self.param_convertors = compile_path(path)


class _RouteAdapter:
    _routes: Routes
    _wrapped_app: t.Optional[ASGIApp]
    _base_app: t.Optional[ASGIApp]
    _middleware: t.Sequence[Middleware]

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert self._wrapped_app  # silence mypy
        await self._wrapped_app(scope, receive, send)

    def _initialize_apps(self) -> None:
        self._base_app = self._create_base_asgi_app()
        self._wrapped_app = self._apply_middleware(self._base_app)

    def _create_base_asgi_app(self) -> ASGIApp:
        raise NotImplementedError()

    def _apply_middleware(self, app: ASGIApp) -> ASGIApp:
        return apply_middleware(app, self._middleware)

    def __enter__(self) -> Routes:
        self._wrapped_app = None  # force app recreation when routes changed
        return self._routes

    def __exit__(self, *args: t.Any) -> None:
        pass

    def __getattr__(self, item: str) -> t.Any:
        try:
            return getattr(self._base_app, item)
        except AttributeError:
            self._initialize_apps()
            return getattr(self._base_app, item)


class HostRoutes(_RouteAdapter):
    def __init__(
        self,
        host: str,
        routes: t.Union[list[routing.BaseRoute], Routes] = None,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self._host = host
        self._name = name
        self._routes = Routes(routes)
        self._middleware = middleware or []
        self._wrapped_app: t.Optional[ASGIApp] = None
        self._base_app: t.Optional[routing.Host] = None

    def _create_base_asgi_app(self) -> ASGIApp:
        return routing.Host(host=self._host, app=Router(routes=self._routes), name=self._name)


class GroupRoutes(_RouteAdapter):
    def __init__(
        self,
        prefix: str,
        routes: t.Union[list[routing.BaseRoute], Routes] = None,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self._name = name
        self._prefix = prefix
        self._routes = Routes(routes)
        self._middleware = middleware or []
        self._wrapped_app: t.Optional[ASGIApp] = None
        self._base_app: t.Optional[routing.Mount] = None

    def _apply_middleware(self, app: ASGIApp) -> ASGIApp:
        return app

    def _create_base_asgi_app(self) -> ASGIApp:
        router: ASGIApp = Router(self._routes)
        if self._middleware:
            for mw in reversed(self._middleware):
                router = mw.wrap(router)
        return routing.Mount(path=self._prefix, app=router, name=self._name)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert self._base_app  # silence mypy
        await self._base_app.handle(scope, receive, send)


class ResourceRoute(Route):
    def __init__(self, ):


class Routes(t.Sequence[routing.BaseRoute]):
    def __init__(self, routes: t.Iterable[routing.BaseRoute] = None) -> None:
        self._routes: list[routing.BaseRoute] = list(routes or [])

    def get(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path,
            endpoint,
            name=name,
            methods=['HEAD', 'GET'],
            include_in_schema=include_in_schema,
            middleware=middleware,
        )

    def post(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['POST'], include_in_schema=include_in_schema, middleware=middleware
        )

    def get_or_post(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path,
            endpoint,
            name=name,
            methods=['HEAD', 'GET', 'POST'],
            include_in_schema=include_in_schema,
            middleware=middleware,
        )

    def patch(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['PATCH'], include_in_schema=include_in_schema, middleware=middleware
        )

    def put(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(path, endpoint, name=name, methods=['PUT'], include_in_schema=include_in_schema, middleware=middleware)

    def delete(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['DELETE'], include_in_schema=include_in_schema, middleware=middleware
        )

    def head(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['HEAD'], include_in_schema=include_in_schema, middleware=middleware
        )

    def options(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self.add(
            path, endpoint, name=name, methods=['OPTIONS'], include_in_schema=include_in_schema, middleware=middleware
        )

    def any(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        _all = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"]
        self.add(path, endpoint, name=name, methods=_all, include_in_schema=include_in_schema, middleware=middleware)

    def add(
        self,
        path: str,
        endpoint: t.Callable,
        *,
        methods: t.List[str],
        name: str = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        route = Route(
            path,
            endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
            middleware=middleware,
        )
        self._routes.append(route)

    def websocket(self, path: str, endpoint: t.Callable, *, name: str = None) -> None:
        self._routes.append(WebSocketRoute(path, endpoint, name=name))

    def mount(self, path: str, app: ASGIApp, *, name: str = None) -> None:
        self._routes.append(Mount(path, app, name=name))

    def static(
        self,
        path: str,
        directory: t.Union[str, PathLike[str]] = None,
        *,
        packages: list[str] = None,
        html: bool = False,
        check_dir: bool = True,
        name: str = None,
    ) -> None:
        app = StaticFiles(directory=directory, packages=packages, html=html, check_dir=check_dir)
        self._routes.append(Mount(path, app, name=name))

    def host(
        self,
        host: str,
        routes: t.Union[Routes, list[routing.BaseRoute]] = None,
        *,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> HostRoutes:
        app = HostRoutes(host, routes, name, middleware)
        self._routes.append(t.cast(routing.Host, app))
        return app

    def group(
        self,
        prefix: str,
        routes: t.Union[Routes, list[routing.BaseRoute]] = None,
        *,
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> GroupRoutes:
        app = GroupRoutes(prefix, routes, name, middleware)
        self._routes.append(t.cast(routing.Mount, app))
        return app

    def redirect(self, path: str, destination: str, status_code: int = 307, headers: dict = None) -> None:
        self.mount(
            path,
            RedirectResponse(destination, status_code=status_code, headers=headers),
        )

    _actions = t.Literal['index', 'new', 'create', 'show', 'edit', 'update', 'destroy']

    def resource(
        self,
        path: str,
        resource: Resource,
        *,
        name: str = None,
        only: list[_actions] = None,
        exclude: list[_actions] = None,
        include_in_schema: bool = True,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        assert bool(only and exclude) is False, '"exclude" and "only" arguments are mutually exclusive.'
        allowed = ['index', 'new', 'create', 'show', 'edit', 'update', 'destroy']
        if only:
            allowed = [action for action in allowed if action in only]
        if exclude:
            allowed = [action for action in allowed if action not in exclude]

        collection_method_map = {
            'head': resource.index,
            'get': resource.index,
            'post': resource.create,
        }
        object_method_map = {
            'head': resource.index,
            'get': resource.show,
            'put': resource.update,
            'patch': resource.update,
            'delete': resource.destroy,
        }

        async def resource_list_view(request: Request) -> Response:
            method = request.method.lower()
            return await collection_method_map[method](request)

        async def resource_object_view(request: Request) -> Response:
            method = request.method.lower()
            return await object_method_map[method](request)

        name = name or resource.__class__.__name__.lower().replace('resource', '')
        with self.group(path) as resource_urls:
            object_route_methods: list[str] = []
            collection_route_methods: list[str] = []

            if 'new' in allowed:
                resource_urls.get('/new', resource.new, name=f'{name}.new')

            if 'edit' in allowed:
                resource_urls.get('/{id}/edit', resource.edit, name=f'{name}.edit')

            if 'index' in allowed:
                collection_route_methods.extend(['HEAD', 'GET'])
            if 'create' in allowed:
                collection_route_methods.append('POST')
            if collection_route_methods:
                resource_urls.add(
                    '/',
                    resource_list_view,
                    methods=collection_route_methods,
                    name=f'{name}.list',
                    include_in_schema=include_in_schema,
                    middleware=middleware,
                )

            if 'show' in allowed:
                object_route_methods.extend(['HEAD', 'GET'])
            if 'update' in allowed:
                object_route_methods.extend(['PUT', 'PATCH'])
            if 'destroy' in allowed:
                object_route_methods.append('DELETE')
            if object_route_methods:
                resource_urls.add(
                    '/{id}',
                    resource_object_view,
                    methods=object_route_methods,
                    name=f'{name}.detail',
                    include_in_schema=include_in_schema,
                    middleware=middleware,
                )

    def __iter__(self) -> t.Iterator[routing.BaseRoute]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __getitem__(self, item: t.Any) -> t.Any:  # pragma: nocover
        """Added to implement Sequence protocol."""
        raise NotImplementedError

    def __contains__(self, route: object) -> t.Any:  # pragma: nocover
        raise NotImplementedError
