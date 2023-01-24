import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from kupala.contrib.sqlalchemy import SQLAlchemy
from tests.contrib.sqlalchemy.conftest import DATABASE_URL


@pytest.fixture
def extension() -> SQLAlchemy:
    return SQLAlchemy(DATABASE_URL)


@pytest.mark.asyncio
async def test_new_session(extension: SQLAlchemy) -> None:
    async with extension.new_session() as session:
        assert isinstance(session, AsyncSession)


@pytest.mark.asyncio
async def test_custom_session_class() -> None:
    class Session(AsyncSession):
        ...

    extension = SQLAlchemy(DATABASE_URL, session_class=Session)
    async with extension.new_session() as session:
        assert isinstance(session, Session)


@pytest.mark.asyncio
async def test_custom_metadata() -> None:
    metadata = MetaData()

    extension = SQLAlchemy(DATABASE_URL, metadata=metadata)
    assert extension.metadata == metadata
