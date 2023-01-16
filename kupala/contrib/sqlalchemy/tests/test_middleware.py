from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from kupala.contrib.sqlalchemy import DbSessionMiddleware


def test_dbsession_middleware_injects_session_to_state(db_sessionmaker: async_sessionmaker) -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("yes" if "db" in scope["state"] else "no")
        await response(scope, receive, send)

    app = DbSessionMiddleware(app, async_session=db_sessionmaker)
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "yes"
