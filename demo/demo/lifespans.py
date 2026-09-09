import contextlib
import typing

from demo.models import Catalog
from kupala.applications import Kupala


@contextlib.asynccontextmanager
async def open_catalog(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
    yield {"catalog": Catalog()}


@contextlib.asynccontextmanager
async def announce(app: Kupala) -> typing.AsyncGenerator[None]:
    # what an extension looks like: it contributes no state, only startup and shutdown work
    print("DEMO UP")
    try:
        yield None
    finally:
        print("DEMO DOWN")
