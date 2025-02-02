import os
import pytest
import typing
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from kupala.contrib.sqlalchemy.manager import DatabaseManager
from tests.contrib.sqlalchemy.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite://")


@pytest.fixture(scope="session")
async def db_engine() -> typing.AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def db_manager() -> typing.AsyncGenerator[DatabaseManager, None]:
    manager = DatabaseManager(dangerously_disable_pool=True, url=DATABASE_URL)
    async with manager:
        yield manager


@pytest.fixture
async def db_session(
    db_manager: DatabaseManager,
) -> typing.AsyncGenerator[AsyncSession, None]:
    async with db_manager.session(force_rollback=True) as session:
        yield session


@pytest.fixture(autouse=True, scope="session")
async def setup_database(db_engine: AsyncEngine) -> typing.AsyncGenerator[None, None]:
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
