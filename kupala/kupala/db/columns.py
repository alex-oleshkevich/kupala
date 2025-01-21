import datetime
import typing
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

IntPk = typing.Annotated[int, mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)]
StrPk = typing.Annotated[str, mapped_column(sa.Text, primary_key=True)]
UUIDPk = typing.Annotated[uuid.UUID, mapped_column(sa.UUID(), primary_key=True, default=uuid.uuid4)]
Text = typing.Annotated[str, mapped_column(sa.Text())]
DefaultText = typing.Annotated[str, mapped_column(sa.Text(), default="", server_default="")]
DateTimeTz = typing.Annotated[datetime.datetime, mapped_column(sa.DateTime(timezone=True))]
DefaultInt = typing.Annotated[int, mapped_column(sa.Integer, default=0, server_default="0")]
DefaultString = typing.Annotated[str, mapped_column(sa.String, default="", server_default="")]
AutoCreatedAt = typing.Annotated[
    datetime.datetime,
    mapped_column(
        sa.DateTime(timezone=True),
        default=datetime.datetime.now,
        server_default=sa.func.now(),
        nullable=False,
    ),
]
AutoUpdatedAt = typing.Annotated[
    datetime.datetime,
    mapped_column(
        sa.DateTime(timezone=True),
        default=datetime.datetime.now,
        server_default=sa.func.now(),
        nullable=False,
        onupdate=datetime.datetime.now,
        server_onupdate=sa.func.now(),
    ),
]
