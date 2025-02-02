import typing

from sqlalchemy.ext.asyncio import AsyncSession

from kupala.contrib.sqlalchemy.query import Query

DbSession = typing.Annotated[AsyncSession, lambda r: r.state.dbsession]
DbQuery = typing.Annotated[Query, lambda r: Query(r.state.dbsession)]
