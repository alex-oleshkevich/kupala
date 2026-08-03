import typing

from starlette.routing import Route as BaseRoute

from kupala.middleware import Middleware
from kupala.requests import Request
from kupala.responses import Response

type SyncEndpoint = typing.Callable[[Request], Response]
type AsyncEndpoint = typing.Callable[[Request], typing.Awaitable[Response]]
type ViewEndpoint = SyncEndpoint | AsyncEndpoint


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        name: str | None = None,
        methods: typing.Sequence[str] = ("get"),
        middleware: typing.Sequence[Middleware] = (),
    ) -> None:
        super().__init__(path, endpoint, name=name, methods=list(methods))
        self._middleware = middleware


class Routes:
    def __init__(
        self,
        routes: typing.Sequence[Route | typing.Self] = (),
        prefix: str = "",
        middleware: typing.Sequence[Middleware] = (),
        namespace: str = "",
    ) -> None:
        self.routes = list(routes)
        self.prefix = prefix
        self.namespace = namespace
        self.middleware = list(middleware)

    def add(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        name: str | None = None,
        methods: typing.Sequence[str],
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        namespace = self.namespace + "." if self.namespace else ""
        self.routes.append(
            Route(
                path=self.prefix.removesuffix("/") + "/" + path.removeprefix("/"),
                endpoint=endpoint,
                methods=methods,
                name=namespace + (name or endpoint.__name__),
                middleware=self.middleware + list(middleware),
            )
        )
        return endpoint

    def get(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["GET", "HEAD"],
            middleware=middleware,
        )

    def post(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["POST"],
            middleware=middleware,
        )

    def get_or_post(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["GET", "HEAD", "POST"],
            middleware=middleware,
        )

    def put(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["PUT"],
            middleware=middleware,
        )

    def patch(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["PATCH"],
            middleware=middleware,
        )

    def delete(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["DELETE"],
            middleware=middleware,
        )

    def head(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["HEAD"],
            middleware=middleware,
        )

    def query(
        self,
        path: str,
        endpoint: ViewEndpoint,
        *,
        middleware: typing.Sequence[Middleware] = (),
    ) -> ViewEndpoint:
        return self.add(
            path=path,
            endpoint=endpoint,
            methods=["QUERY"],
            middleware=middleware,
        )
