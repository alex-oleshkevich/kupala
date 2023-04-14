import contextlib
import typing
from starlette.applications import AppType, Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute

from kupala import console
from kupala.extensions import Extension

ExceptionHandlersType = typing.Mapping[
    typing.Any,
    typing.Callable[
        [Request, Exception],
        typing.Union[Response, typing.Awaitable[Response]],
    ],
]


class Kupala(Starlette):
    def __init__(
        self: AppType,
        debug: bool = False,
        routes: typing.Sequence[BaseRoute] | None = None,
        middleware: typing.Sequence[Middleware] | None = None,
        exception_handlers: ExceptionHandlersType | None = None,
        extensions: typing.Sequence[Extension] | None = None,
    ) -> None:
        @contextlib.asynccontextmanager
        async def lifespan_handler(app: AppType) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
            async with contextlib.AsyncExitStack() as stack:
                full_state: dict[str, typing.Any] = {}
                extension_state: typing.Mapping[str, typing.Any] | None

                for extension in extensions or []:
                    extension_state = await stack.enter_async_context(extension.bootstrap(app))
                    if extension_state:
                        full_state.update(extension_state)

                yield full_state

        super().__init__(
            debug=debug,
            routes=routes,
            middleware=middleware,
            exception_handlers=exception_handlers,
            lifespan=lifespan_handler,
        )

        self.cli = console.create_console_app(self)
