from __future__ import annotations

import typing

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette_sqlalchemy import (
    Collection,
    DbSessionMiddleware,
    MultipleResultsError,
    NoResultError,
    Query,
    query,
)

from kupala.extensions import Extension

__all__ = [
    "SQLAlchemy",
    "Query",
    "query",
    "NoResultError",
    "MultipleResultsError",
    "DbSessionMiddleware",
    "Collection",
]


class SQLAlchemy(Extension):
    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
        pool_size: int = 5,
        pool_pre_ping: bool = True,
        pool_timeout: int = 30,
        max_overflow: int = 10,
        engine_kwargs: dict[str, typing.Any] | None = None,
        sync_engine_kwargs: dict[str, typing.Any] | None = None,
    ) -> None:
        engine_kwargs = dict(
            echo=echo,
            pool_size=pool_size,
            pool_timeout=pool_timeout,
            pool_pre_ping=pool_pre_ping,
            isolation_level="READ COMMITTED",
            max_overflow=max_overflow,
            **(engine_kwargs or {}),
        )
        sync_engine_kwargs = sync_engine_kwargs or engine_kwargs
        self.engine = create_async_engine(url, **engine_kwargs)
        self.sync_engine = create_engine(url, **sync_engine_kwargs)

        self.new_session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.new_sync_session = sessionmaker(self.sync_engine)
