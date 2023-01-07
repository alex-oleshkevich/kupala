import sqlalchemy as sa
import typing
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.middleware import Middleware

from kupala.contrib.sqlalchemy.middleware import DbSessionMiddleware

DEFAULT_NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "ux": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class SQLAlchemy:
    def __init__(
        self,
        database_url: str,
        engine_options: dict[str, typing.Any] | None = None,
    ) -> None:
        engine_options = engine_options or {}
        self.database_url = database_url
        self.engine = create_async_engine(database_url, **engine_options)
        self.async_session = async_sessionmaker(self.engine)
        self.metadata = sa.MetaData(naming_convention=DEFAULT_NAMING_CONVENTION)
        self.schema = Schema(self)

    def setup(self, app: Starlette) -> None:
        app.state.db = self
        app.user_middleware.insert(0, Middleware(DbSessionMiddleware, async_session=self.async_session))
        app.middleware_stack = app.build_middleware_stack()


class Schema:
    def __init__(self, db: SQLAlchemy) -> None:
        self.db = db

    async def create_all(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(self.db.metadata.create_all)

    async def drop_all(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(self.db.metadata.drop_all)
