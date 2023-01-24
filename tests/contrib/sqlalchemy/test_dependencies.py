import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.testclient import TestClient

from kupala.contrib.sqlalchemy import DbQuery, DbSession, DbSessionMiddleware, SQLAlchemy
from kupala.dependencies import DependencyError, DependencyResolver, InvokeContext
from kupala.routing import route
from tests.contrib.sqlalchemy.conftest import DATABASE_URL


def test_resolves_dbsession(db_sessionmaker: async_sessionmaker) -> None:
    @route("/")
    def index(request: Request, db: DbSession) -> Response:
        return PlainTextResponse(db.__class__.__name__)

    app = Starlette(routes=[index], middleware=[Middleware(DbSessionMiddleware, async_session=db_sessionmaker)])
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "AsyncSession"


@pytest.mark.asyncio
async def test_resolves_dbsession_from_app(db_sessionmaker: async_sessionmaker) -> None:
    """
    In CLI context there is no Request.

    Instead, we have to create session from the app instance.
    """

    def fn(dbsession: DbSession) -> str:
        return dbsession.__class__.__name__

    db = SQLAlchemy(database_url=DATABASE_URL)
    app = Starlette()
    db.setup(app)
    plan = DependencyResolver.from_callable(fn)
    result = await plan.execute(InvokeContext(request=None, app=app))
    assert result == "AsyncSession"


@pytest.mark.asyncio
async def test_fails_to_resolve_dbsession(db_sessionmaker: async_sessionmaker) -> None:
    def fn(dbsession: DbSession) -> None:
        ...

    with pytest.raises(DependencyError, match="Cannot obtain"):
        app = Starlette()
        plan = DependencyResolver.from_callable(fn)
        await plan.execute(InvokeContext(request=None, app=app))


def test_resolves_dbquery(db_sessionmaker: async_sessionmaker) -> None:
    @route("/")
    def index(request: Request, db: DbSession, query: DbQuery) -> Response:
        assert query.session == db
        return PlainTextResponse(query.__class__.__name__)

    app = Starlette(routes=[index], middleware=[Middleware(DbSessionMiddleware, async_session=db_sessionmaker)])
    client = TestClient(app)
    response = client.get("/")
    assert response.text == "Query"
