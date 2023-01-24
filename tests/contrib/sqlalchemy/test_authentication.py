from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from kupala.contrib.sqlalchemy.authentication import UserLoader
from tests.contrib.sqlalchemy.models import User


async def test_user_loader(db_session: AsyncSession) -> None:
    user = User(email="root@localhost")
    db_session.add(user)
    await db_session.commit()
    loader = UserLoader(user_model_class=User, pk_column="id")

    conn = HTTPConnection({"type": "http"})
    conn.state.db = db_session

    loaded_user = await loader(conn, str(user.id))
    assert user == loaded_user

    assert not await loader(conn, "-1")
