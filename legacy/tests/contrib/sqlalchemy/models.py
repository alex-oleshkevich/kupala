import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from kupala.contrib.sqlalchemy.models import Base, WithTimestamps


class User(Base, WithTimestamps):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(sa.String, default="root@localhost")
    name: Mapped[str] = mapped_column(sa.String, default="user")
    password: Mapped[str] = mapped_column(sa.String, default="")
