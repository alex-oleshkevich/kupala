import datetime
import typing

from asgiref.typing import Scope

from kupala.middleware import Middleware
from kupala.requests import Request, Websocket
from kupala.responses import Response

type IntoResponse = (
    str
    | bytes
    | dict[str, typing.Any]
    | list[typing.Any]
    | None
    | typing.AsyncIterable[bytes]
    | typing.AsyncIterable[str]
    | typing.IO[bytes]
)
type TwoTupleResponse = tuple[IntoResponse, int]
type ThreeTupleResponse = tuple[IntoResponse, int, typing.Mapping[str, str]]
type HandlerResponse = Response | IntoResponse | TwoTupleResponse | ThreeTupleResponse

type SyncHandler = typing.Callable[[Request], HandlerResponse]
type AsyncHandler = typing.Callable[[Request], typing.Awaitable[HandlerResponse]]
type WebsocketHandler = typing.Callable[[Websocket], typing.Awaitable[None]]
type EndpointHandler = SyncHandler | AsyncHandler

type HTTPMethod = typing.Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "QUERY", "OPTIONS", "TRACE"]

type RouteDecorator = typing.Callable[[EndpointHandler], EndpointHandler]
type WebSocketDecorator = typing.Callable[[WebsocketHandler], WebsocketHandler]
type AnyRoute = Route | WebSocketRoute


class Route:
    def __init__(
        self,
        path: str,
        endpoint: EndpointHandler,
        *,
        methods: typing.Sequence[HTTPMethod],
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> None:
        self.path = path
        self.endpoint = endpoint
        self.methods = methods
        self.name = name
        self.middleware = list(middleware)
        self.metadata = metadata or {}
        self.max_body_size = max_body_size
        self.timeout = timeout


class WebSocketRoute:
    def __init__(
        self,
        path: str,
        endpoint: WebsocketHandler,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        timeout: datetime.timedelta | None = None,
        metadata: dict[str, typing.Any] | None = None,
    ) -> None:
        self.path = path
        self.endpoint = endpoint
        self.name = name or getattr(endpoint, "__name__", None)
        self.middleware = list(middleware)
        self.timeout = timeout
        self.metadata = metadata or {}


class RouteGroup:
    def __init__(
        self,
        routes: typing.Sequence[AnyRoute] = (),
        *,
        name: str | None = None,
        prefix: str = "",
        middleware: typing.Sequence[Middleware] = (),
    ) -> None:
        self.name = name
        self.prefix = prefix.removesuffix("/")
        self.routes: list[AnyRoute] = list(routes)
        self.middleware = list(middleware)

    def add(
        self,
        path: str,
        *,
        methods: typing.Sequence[HTTPMethod],
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        def decorator(endpoint: EndpointHandler) -> EndpointHandler:
            self.routes.append(
                Route(
                    path=self.prefix + "/" + path.removeprefix("/"),
                    endpoint=endpoint,
                    methods=methods,
                    name=name,
                    middleware=self.middleware + list(middleware),
                    metadata=metadata,
                    max_body_size=max_body_size,
                    timeout=timeout,
                )
            )
            return endpoint

        return decorator

    def websocket(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> WebSocketDecorator:
        def decorator(endpoint: WebsocketHandler) -> WebsocketHandler:
            self.routes.append(
                WebSocketRoute(
                    path=self.prefix + "/" + path.removeprefix("/"),
                    endpoint=endpoint,
                    name=name,
                    middleware=self.middleware + list(middleware),
                    metadata=metadata,
                    timeout=timeout,
                )
            )
            return endpoint

        return decorator

    def get(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("GET", "HEAD"),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )

    def head(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("HEAD",),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )

    def post(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("POST",),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )

    def put(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("PUT",),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )

    def patch(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("PATCH",),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )

    def delete(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("DELETE",),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )

    def query(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("QUERY",),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )

    def get_or_post(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: typing.Sequence[Middleware] = (),
        metadata: dict[str, typing.Any] | None = None,
        max_body_size: int | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> RouteDecorator:
        return self.add(
            path,
            methods=("GET", "HEAD", "POST"),
            name=name,
            middleware=middleware,
            metadata=metadata,
            max_body_size=max_body_size,
            timeout=timeout,
        )


class Router:
    def __init__(self, routes: RouteGroup) -> None:
        self._table: dict[str, Route] = {}

    def match(self, scope: Scope) -> Route | WebSocketRoute | None:
        pass
