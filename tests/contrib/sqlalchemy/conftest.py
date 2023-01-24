import os
import pytest
import typing
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from tests.contrib.sqlalchemy.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1/kupala_test")


@pytest.fixture(scope="session")
async def db_engine() -> typing.AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def db_sessionmaker(db_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(db_sessionmaker: async_sessionmaker) -> typing.AsyncGenerator[AsyncSession, None]:
    async with db_sessionmaker() as session:
        yield session


@pytest.fixture(autouse=True, scope="session")
async def setup_database(db_engine: AsyncEngine) -> typing.AsyncGenerator[None, None]:
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
