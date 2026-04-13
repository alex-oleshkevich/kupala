import contextlib
import typing

from kupala.applications import Kupala
from kupala.contrib.sqlalchemy.columns import (
    AutoCreatedAt,
    AutoUpdatedAt,
    DateTimeTz,
    DefaultInt,
    DefaultString,
    DefaultText,
    IntPk,
    UUIDPk,
)
from kupala.contrib.sqlalchemy.factories import AsyncSQLAlchemyModelFactory
from kupala.contrib.sqlalchemy.manager import DatabaseManager
from kupala.contrib.sqlalchemy.middleware import DbSessionMiddleware
from kupala.contrib.sqlalchemy.migrations import RendersMigrationType
from kupala.contrib.sqlalchemy.models import Base, WithTimestamps
from kupala.contrib.sqlalchemy.query import Query, query
from kupala.contrib.sqlalchemy.dependencies import DbSession, DbQuery

__all__ = [
    "query",
    "IntPk",
    "UUIDPk",
    "AutoUpdatedAt",
    "AutoCreatedAt",
    "DateTimeTz",
    "DefaultInt",
    "DefaultString",
    "DefaultText",
    "DbSessionMiddleware",
    "Query",
    "query",
    "DatabaseManager",
    "Base",
    "WithTimestamps",
    "RendersMigrationType",
    "AsyncSQLAlchemyModelFactory",
    "database_initializer",
    "DbSession",
    "DbQuery",
]


def database_initializer(database: DatabaseManager) -> typing.Callable:
    @contextlib.asynccontextmanager
    async def _initializer(app: Kupala) -> typing.AsyncGenerator[None, None]:
        async with database:
            app.dependencies[DatabaseManager] = database
            yield

    return _initializer
