import pytest
import sqlalchemy as sa
import typing
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock

from kupala.collection import Collection
from kupala.contrib.sqlalchemy.query import Query
from tests.contrib.sqlalchemy.models import User


@pytest.fixture
def query(db_session: AsyncSession) -> typing.Generator[Query, None, None]:
    yield Query(db_session)


@pytest.fixture()
async def user(db_session: AsyncSession) -> typing.AsyncGenerator[User, None]:
    user = User(email="root@localhost")
    db_session.add(user)
    await db_session.commit()
    yield user


async def test_one(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    loaded_user = await query.one(stmt)
    assert loaded_user == user


async def test_one_raises_when_no_objects(query: Query, user: User) -> None:
    with pytest.raises(NoResultFound):
        stmt = sa.select(User).where(User.id == -1)
        await query.one(stmt)


async def test_one_or_none(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    loaded_user = await query.one_or_none(stmt)
    assert loaded_user == user


async def test_one_or_none_returns_none(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == -1)
    assert not await query.one_or_none(stmt)


async def test_one_or_raise(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    loaded_user = await query.one_or_raise(stmt, ValueError())
    assert loaded_user == user


async def test_one_or_raise_raises(query: Query, user: User) -> None:
    with pytest.raises(ValueError, match="RAISED"):
        stmt = sa.select(User).where(User.id == -1)
        assert not await query.one_or_raise(stmt, ValueError("RAISED"))


async def test_one_or_default(query: Query, user: User) -> None:
    default = User()
    stmt = sa.select(User).where(User.id == user.id)
    loaded_user = await query.one_or_default(stmt, default)
    assert loaded_user == user


async def test_one_or_default_returns_default(query: Query, user: User) -> None:
    default = User()
    stmt = sa.select(User).where(User.id == -1)
    assert await query.one_or_default(stmt, default) == default


async def test_all(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    loaded_users = await query.all(stmt)
    assert loaded_users == Collection([user])


async def test_iterator(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    iterator = query.iterator(stmt)
    mock = MagicMock()
    async for loaded_user in iterator:
        assert loaded_user == user
        mock()
    mock.assert_called()


async def test_exists(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    assert await query.exists(stmt)


async def test_not_exists(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == -1)
    assert not await query.exists(stmt)


async def test_count(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    assert await query.count(stmt) == 1


async def test_paginate(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    page = await query.paginate(stmt)
    assert page.rows == [user]


async def test_choices(query: Query, user: User) -> None:
    stmt = sa.select(User).where(User.id == user.id)
    choices = await query.choices(stmt, label_attr="name")
    assert choices == [(user.id, user.name)]
