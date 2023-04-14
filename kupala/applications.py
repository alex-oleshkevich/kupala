import anyio
import contextlib
import sys
import typing
from starlette.applications import Starlette
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
        self,
        debug: bool = False,
        routes: typing.Sequence[BaseRoute] | None = None,
        middleware: typing.Sequence[Middleware] | None = None,
        exception_handlers: ExceptionHandlersType | None = None,
        extensions: typing.Sequence[Extension] | None = None,
    ) -> None:
        super().__init__(
            debug=debug,
            routes=routes,
            middleware=middleware,
            exception_handlers=exception_handlers,
            lifespan=self.bootstrap,
        )

        self.extensions = extensions or []
        self.cli = console.Group()

    @contextlib.asynccontextmanager
    async def bootstrap(self, *args: typing.Any) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
        async with contextlib.AsyncExitStack() as stack:
            full_state: dict[str, typing.Any] = {}
            extension_state: typing.Mapping[str, typing.Any] | None

            for extension in self.extensions:
                if extension_state := await stack.enter_async_context(extension.bootstrap(self)):
                    full_state.update(extension_state)

            yield full_state

    def run_cli(self) -> int:
        async def main() -> int:
            async with self.bootstrap():
                self.cli.populate_from_entrypoints()
                context = console.ConsoleContext(app=self)
                return self.cli.main(sys.argv[1:], obj=context)

        return anyio.run(main)
