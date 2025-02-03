import contextlib
import contextvars
import typing

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kupala.extensions import Extension


class DatabaseManager(Extension):
    def __init__(
        self,
        url: str,
        *,
        pool_pre_ping: bool = False,
        pool_size: int = 15,
        pool_recycle: int = 1000,
        pool_timeout: int = 10,
        max_overflow: int = 2,
        echo: bool = False,
        isolation_level: str = "READ COMMITTED",
        dangerously_disable_pool: bool = False,
    ) -> None:
        self._url = url
        self._echo = echo
        self._pool_size = pool_size
        self._pool_pre_ping = pool_pre_ping
        self._pool_recycle = pool_recycle
        self._pool_timeout = pool_timeout
        self._max_overflow = max_overflow
        self._dangerously_disable_pool = dangerously_disable_pool
        self._isolation_level = isolation_level
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None
        self._current_session: contextvars.ContextVar[AsyncSession] = contextvars.ContextVar("sqla_current_session")

    async def __aenter__(self) -> typing.AsyncGenerator[AsyncEngine, None]:
        if self._engine is not None:
            return self._engine

        opts = dict(
            pool_size=self._pool_size,
            pool_recycle=self._pool_recycle,
            pool_timeout=self._pool_timeout,
            max_overflow=self._max_overflow,
        )
        if self._dangerously_disable_pool:
            opts = {"poolclass": NullPool}

        self._engine = create_async_engine(
            self._url,
            echo=self._echo,
            pool_pre_ping=self._pool_pre_ping,
            isolation_level=self._isolation_level,
            **opts,
        )
        self._sessionmaker = async_sessionmaker(bind=self._engine, expire_on_commit=False)
        return self._engine

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self._engine.dispose()

    @property
    def current_session(self) -> AsyncSession:
        """Return the currently active session if it exists.
        Prefer not to use this method, only for debugging and special purposes.
        Raises ValueError if no session is active."""
        try:
            return self._current_session.get()
        except LookupError:
            raise ValueError("No SQLAlchemy session is currently active.")

    @contextlib.asynccontextmanager
    async def session(self, force_rollback: bool = False) -> typing.AsyncGenerator[AsyncSession, None]:
        """Get a new session instance.
        If force_rollback is True, the session will be rolled back after exiting the context."""
        assert self._sessionmaker is not None, "SQLAlchemy engine is not initialized."

        if force_rollback:
            async with self._start_rollback_session() as session:
                self._current_session.set(session)
                yield session
        else:
            async with self._start_normal_session() as session:
                self._current_session.set(session)
                yield session

    @contextlib.asynccontextmanager
    async def _start_normal_session(self, **kwargs: typing.Any) -> typing.AsyncGenerator[AsyncSession, None]:
        async with self._sessionmaker(**kwargs) as session:
            yield session

    @contextlib.asynccontextmanager
    async def _start_rollback_session(
        self,
    ) -> typing.AsyncGenerator[AsyncSession, None]:
        """Create a new session that will be rolled back after exiting the context.
        For testing purposes. Any BEGIN/COMMIT/ROLLBACK ops are executed in SAVEPOINT.
        See https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites"""
        async with self._engine.connect() as conn:
            async with conn.begin() as tx:
                async with self._start_normal_session(bind=conn, join_transaction_mode="create_savepoint") as session:
                    try:
                        yield session
                    finally:
                        await tx.rollback()
