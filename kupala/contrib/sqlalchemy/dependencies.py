import typing
from sqlalchemy.ext.asyncio import AsyncSession

from kupala.contrib.sqlalchemy.query import Query

DbSession = typing.Annotated[AsyncSession, lambda context: context.request.state.db]
DbQuery = typing.Annotated[Query, lambda context: Query(context.request.state.db)]
