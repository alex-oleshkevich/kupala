import typing as t
from contextlib import asynccontextmanager

from kupala.application import Kupala
from kupala.testclient import TestClient


def test_calls_lifespan_callbacks() -> None:
    startup_complete = False
    cleanup_complete = False

    @asynccontextmanager
    async def lifespan(app: Kupala) -> t.AsyncGenerator[None, None]:
        nonlocal startup_complete, cleanup_complete
        startup_complete = True
        yield
        cleanup_complete = True

    app = Kupala(
        lifespan_handlers=[lifespan]
    )

    with TestClient(app):
        assert startup_complete
        assert not cleanup_complete

    assert startup_complete
    assert cleanup_complete
