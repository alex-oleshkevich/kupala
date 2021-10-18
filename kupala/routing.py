from __future__ import annotations

import typing as t
from os import PathLike

from starlette import routing
from starlette.routing import Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.middleware import Middleware
from kupala.responses import RedirectResponse
from kupala.utils import pipe


class Router(routing.Router):
    pass


class Route(routing.Route):
    pass


class HostRoutes:

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
        self._middleware = middleware
        self._app: t.Optional[ASGIApp] = None
        self._app_ref: t.Optional[ASGIApp] = None

    @property
    def app(self) -> ASGIApp:
        if self._app is None:
            self._create_app()
        return self._app

    def _create_app(self) -> None:
        self._app_ref = self._create_base_asgi_app()
        self._app = self._app_ref
        if self._middleware:
            for mw in reversed(self._middleware):
                self._app = mw.wrap(self._app)

    def _create_base_asgi_app(self) -> ASGIApp:
        return routing.Host(host=self._host, app=Router(routes=self._routes), name=self._name)

    def __enter__(self) -> Routes:
        self._app = None  # force app recreation when routes changed
        return self._routes

    def __exit__(self, *args: t.Any) -> None:
        pass

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._app(scope, receive, send)

    def __getattr__(self, item: str) -> t.Any:
        try:
            return getattr(self._app_ref, item)
        except AttributeError:
            self._create_app()
            return getattr(self._app_ref, item)


class GroupRoutes:
    def __init__(
        self,
        prefix: str,
        routes: t.Union[list[routing.BaseRoute], Routes],
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> None:
        self._name = name
        self._prefix = prefix
        self._routes = Routes(routes)
        self._middleware = middleware
        self._app: t.Optional[ASGIApp] = None
        self._app_ref: t.Optional[ASGIApp] = None

    @property
    def app(self) -> ASGIApp:
        if self._app is None:
            self._app = routing.Mount(path=self._prefix, app=Router(self._routes), name=self._name)
        return self._app

    # @property
    # def app(self) -> ASGIApp:
    #     if self._app is None:
    #         self._create_app()
    #     return self._app
    #
    # def _create_app(self) -> None:
    #     self._app_ref = self._create_base_asgi_app()
    #     self._app = self._app_ref
    #     if self._middleware:
    #         for mw in reversed(self._middleware):
    #             self._app = mw.wrap(self._app)
    #
    # def _create_base_asgi_app(self) -> ASGIApp:
    #     return routing.Host(host=self._host, app=Router(routes=self._routes), name=self._name)

    # async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
    #     await self._app(scope, receive, send)
    #
    # def __getattr__(self, item: str) -> t.Any:
    #     try:
    #         return getattr(self._app_ref, item)
    #     except AttributeError:
    #         self._create_app()
    #         return getattr(self._app_ref, item)

    def __enter__(self) -> Routes:
        self._app = None  # force app recreation when routes changed
        return self._routes

    def __exit__(self, *args: t.Any) -> None:
        pass

    def __getattr__(self, item: str) -> t.Any:
        return getattr(self.app, item)


class Routes:
    def __init__(self, routes: t.List[routing.BaseRoute] = None) -> None:
        self._routes: t.List[routing.BaseRoute] = routes or []

    def get(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['HEAD', 'GET'], include_in_schema=include_in_schema)

    def post(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['POST'], include_in_schema=include_in_schema)

    def get_or_post(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['HEAD', 'GET', 'POST'], include_in_schema=include_in_schema)

    def patch(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['PATCH'], include_in_schema=include_in_schema)

    def put(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['PUT'], include_in_schema=include_in_schema)

    def delete(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['DELETE'], include_in_schema=include_in_schema)

    def head(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['HEAD'], include_in_schema=include_in_schema)

    def options(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        self.add(path, endpoint, name=name, methods=['OPTIONS'], include_in_schema=include_in_schema)

    def any(self, path: str, endpoint: t.Callable, name: str = None, include_in_schema: bool = True) -> None:
        _all = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"]
        self.add(path, endpoint, name=name, methods=_all, include_in_schema=include_in_schema)

    def add(self, path: str, endpoint: t.Callable, *, methods: t.List[str], name: str = None,
            include_in_schema: bool = True) -> None:
        route = Route(path, endpoint, methods=methods, name=name, include_in_schema=include_in_schema)
        self._routes.append(route)

    def websocket(self, path: str, endpoint: t.Callable, name: str = None) -> None:
        self._routes.append(WebSocketRoute(path, endpoint, name=name))

    def mount(self, path: str, app: ASGIApp, name: str = None) -> None:
        self._routes.append(Mount(path, app, name=name))

    def static(
        self,
        path: str,
        directory: t.Union[str, PathLike[str]] = None,
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
        name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> HostRoutes:
        app = HostRoutes(host, routes, name, middleware)
        self._routes.append(t.cast(routing.Host, app))
        return app

    def group(
        self, prefix: str, routes: t.Union[Routes, list[routing.BaseRoute]] = None, name: str = None,
        middleware: t.Sequence[Middleware] = None,
    ) -> GroupRoutes:
        app = GroupRoutes(prefix, routes, name, middleware)
        self._routes.append(t.cast(routing.Mount, app))
        return app

    def redirect(self, path: str, destination: str, status_code: int = 307, headers: dict = None) -> None:
        self.mount(
            path, RedirectResponse(destination, status_code=status_code, headers=headers),
        )

    def __iter__(self) -> t.Iterator[routing.BaseRoute]:
        return iter(self._routes)

    def __len__(self) -> int:
        return len(self._routes)

    def __getitem__(self, item: t.Any) -> t.Any:  # pragma: nocover
        raise NotImplementedError
