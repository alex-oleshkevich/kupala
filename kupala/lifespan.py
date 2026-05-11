import contextlib
import traceback
import typing

from kupala.types import ASGIApp, Receive, Scope, Send

if typing.TYPE_CHECKING:
    from kupala.app import Kupala


type Lifespan = typing.Callable[
    [Kupala], contextlib.AbstractAsyncContextManager[typing.Mapping[str, typing.Any] | None]
]


def lifespan_handler(app: Kupala, lifespan: typing.Sequence[Lifespan]) -> ASGIApp:
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        await receive()

        started = False
        try:
            async with contextlib.AsyncExitStack() as stack:
                for lf in lifespan:
                    if state := await stack.enter_async_context(lf(app)):
                        scope["state"].update(state)

                await send({"type": "lifespan.startup.complete"})
                started = True

                await receive()

        except Exception:
            text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": text})
            else:
                await send({"type": "lifespan.startup.failed", "message": text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})

    return middleware
