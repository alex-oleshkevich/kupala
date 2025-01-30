import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True
    __repr_field__: str | None = None
    metadata = sa.MetaData()

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
