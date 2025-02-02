from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from kupala.contrib.sqlalchemy import DbSessionMiddleware
from kupala.contrib.sqlalchemy.manager import DatabaseManager


async def test_dbsession_middleware_injects_session_to_state(
    db_manager: DatabaseManager,
) -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("yes" if "dbsession" in scope["state"] else "no")
        await response(scope, receive, send)

    app = DbSessionMiddleware(app, manager=db_manager)
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "yes"
