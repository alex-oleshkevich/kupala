from contextlib import asynccontextmanager

from starlette.testclient import TestClient


def test_calls_lifespan_callbacks(app, test_client):
    startup_complete = False
    cleanup_complete = False

    @asynccontextmanager
    async def lifespan(app):
        nonlocal startup_complete, cleanup_complete
        startup_complete = True
        yield
        cleanup_complete = True

    app.lifecycle.append(lifespan)
    with TestClient(app):
        assert startup_complete
        assert not cleanup_complete

    assert startup_complete
    assert cleanup_complete
