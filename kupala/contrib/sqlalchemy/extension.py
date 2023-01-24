import contextlib
import typing
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.applications import Starlette

NAMING_CONVENTION: dict[str, str] = {
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
        session_class: type[AsyncSession] = AsyncSession,
        sessionmaker_options: dict[str, typing.Any] | None = None,
        metadata: MetaData | None = None,
    ) -> None:
        engine_options = engine_options or {}
        self.engine = create_async_engine(database_url, **engine_options)

        sessionmaker_options = sessionmaker_options or {}
        sessionmaker_options.setdefault("class_", session_class)
        sessionmaker_options.setdefault("expire_on_commit", False)
        self.async_session_factory = async_sessionmaker(self.engine, **sessionmaker_options)
        self.metadata = metadata or MetaData(naming_convention=NAMING_CONVENTION)

    def setup(self, app: Starlette) -> None:
        app.state.sqlalchemy_ext = self

    @contextlib.asynccontextmanager
    async def new_session(self) -> typing.AsyncGenerator[AsyncSession, None]:
        async with self.async_session_factory() as dbsession:
            yield dbsession
