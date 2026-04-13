import sqlalchemy as sa
from kupala.contrib.sqlalchemy import Base, WithTimestamps
from kupala.contrib.sqlalchemy.columns import DateTimeTz, DefaultString, IntPk
from sqlalchemy.orm import Mapped, mapped_column


class User(Base, WithTimestamps):
    __tablename__ = "users"
    __table_args__ = (sa.Index("users_email_udx", sa.func.lower("email"), unique=True),)

    id: Mapped[IntPk]
    name: Mapped[DefaultString]
    email: Mapped[str]
    password: Mapped[str]
    deactivated_at: Mapped[DateTimeTz | None]
    email_verified_at: Mapped[DateTimeTz | None] = mapped_column(doc="Time the user confirmed their email.")
