from sqlalchemy.ext.asyncio import AsyncSession

from tests.contrib.sqlalchemy.models import User


async def test_timestamps_created_at(db_session: AsyncSession) -> None:
    user = User()
    db_session.add(user)
    await db_session.commit()
    assert user.created_at is not None
    assert user.updated_at is not None


async def test_timestamps_update_at_updates_on_change(db_session: AsyncSession) -> None:
    user = User()
    db_session.add(user)
    await db_session.commit()
    base_updated_at = user.updated_at

    user.name = "update"
    await db_session.commit()
    assert user.updated_at != base_updated_at
