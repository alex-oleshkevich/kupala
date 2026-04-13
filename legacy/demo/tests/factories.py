from kupala.contrib.sqlalchemy import AsyncSQLAlchemyModelFactory
from sqlalchemy.ext.asyncio import AsyncSession

from demo.resources import database


def database_session_factory() -> AsyncSession:
    return database.current_session


class BaseModelFactory(AsyncSQLAlchemyModelFactory):
    """Base factory for all SQLAlchemy factories.

    Note, all factories are async, this means you should use `await` when creating an instance.
    Example: `await UserFactory()`"""

    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"
        sqlalchemy_session_factory = database_session_factory
