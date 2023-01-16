import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from kupala.contrib.sqlalchemy.modelmixins import Timestamps


class Base(DeclarativeBase):
    pass


class User(Base, Timestamps):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(sa.String, default="root@localhost")
    name: Mapped[str] = mapped_column(sa.String, default="user")
    password: Mapped[str] = mapped_column(sa.String, default="")
