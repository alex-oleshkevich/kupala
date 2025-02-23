import datetime
import enum
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped

from kupala.contrib.sqlalchemy.columns import AutoCreatedAt, AutoUpdatedAt


class WithTimestamps:
    __abstract__ = True
    created_at: Mapped[AutoCreatedAt]
    updated_at: Mapped[AutoUpdatedAt]


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True
    __repr_field__: str | None = None
    metadata = sa.MetaData()
    type_annotation_map = {
        datetime.datetime: sa.DateTime(timezone=True),
        enum.StrEnum: sa.Text(),
        enum.IntEnum: sa.Integer(),
    }

    def __str__(self) -> str:
        if hasattr(self, "name"):
            return str(self.name)

        if hasattr(self, "title"):
            return str(self.title)
        return "n/a"

    def __repr__(self) -> str:
        pk = [column.name for column in self.__class__.__mapper__.primary_key]
        attrs = self.__repr_field__ or pk
        values = [f'{attr}="{getattr(self, attr)}"' for attr in attrs]
        return f"{self.__class__.__name__}({', '.join(map(str, values))})"
