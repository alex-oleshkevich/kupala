from kupala.contrib.sqlalchemy.dependencies import DbQuery, DbSession
from kupala.contrib.sqlalchemy.middleware import DbSessionMiddleware
from kupala.contrib.sqlalchemy.query import query
from kupala.contrib.sqlalchemy.types import (
    AutoCreatedAt,
    AutoUpdatedAt,
    IntPk,
    JsonDict,
    JsonList,
    LongString,
    ShortString,
    UuidPk,
)

__all__ = [
    "query",
    "DbSession",
    "DbQuery",
    "IntPk",
    "JsonList",
    "JsonDict",
    "AutoUpdatedAt",
    "AutoCreatedAt",
    "ShortString",
    "LongString",
    "UuidPk",
    "DbSessionMiddleware",
    "NAMING_CONVENTION",
]

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "ux": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
