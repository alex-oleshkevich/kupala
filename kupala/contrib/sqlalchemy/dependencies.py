from __future__ import annotations

import contextlib
import typing
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.applications import Starlette
from starlette.requests import Request

from kupala.contrib.sqlalchemy.query import Query
from kupala.dependencies import DependencyError


@contextlib.asynccontextmanager
async def _session_factory(
    request: Request | None = None,
    app: Starlette | None = None,
) -> typing.AsyncGenerator[AsyncSession, None]:
    if request:
        yield request.state.db
        return

    if app and hasattr(app.state, "sqlalchemy_ext"):
        async with app.state.sqlalchemy_ext.new_session() as db_session:
            yield db_session
            return

    raise DependencyError("Cannot obtain database session from request or app.")


def _db_query_factory(session: DbSession) -> Query:
    return Query(session)


DbSession = typing.Annotated[AsyncSession, _session_factory]
DbQuery = typing.Annotated[Query, _db_query_factory]
