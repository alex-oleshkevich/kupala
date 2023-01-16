from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.testclient import TestClient

from kupala.contrib.sqlalchemy import DbQuery, DbSession, DbSessionMiddleware
from kupala.routing import route


def test_resolves_dbsession(db_sessionmaker: async_sessionmaker) -> None:
    @route("/")
    def index(request: Request, db: DbSession) -> Response:
        return PlainTextResponse(db.__class__.__name__)

    app = Starlette(routes=[index], middleware=[Middleware(DbSessionMiddleware, async_session=db_sessionmaker)])
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "AsyncSession"


def test_resolves_dbquery(db_sessionmaker: async_sessionmaker) -> None:
    @route("/")
    def index(request: Request, db: DbSession, query: DbQuery) -> Response:
        assert query.session == db
        return PlainTextResponse(query.__class__.__name__)

    app = Starlette(routes=[index], middleware=[Middleware(DbSessionMiddleware, async_session=db_sessionmaker)])
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "Query"
