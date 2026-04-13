import contextlib
import typing

from sqlalchemy.ext.asyncio import AsyncSession

from kupala.contrib.sqlalchemy.manager import DatabaseManager
from kupala.contrib.sqlalchemy.query import Query


@contextlib.asynccontextmanager
async def _make_dbsession(manager: DatabaseManager) -> typing.AsyncGenerator[AsyncSession, None]:
    async with manager.session() as session:
        yield session


async def _make_dbquery(dbsession: AsyncSession) -> Query:
    return Query(dbsession)


DbSession = typing.Annotated[AsyncSession, _make_dbsession]
DbQuery = typing.Annotated[Query, _make_dbquery]
