import typing
from sqlalchemy.ext.asyncio import AsyncSession

from kupala.contrib.sqlalchemy.query import Query

DbSession = typing.Annotated[AsyncSession, lambda request: request.state.db]
DbQuery = typing.Annotated[Query, lambda request: Query(request.state.db)]
