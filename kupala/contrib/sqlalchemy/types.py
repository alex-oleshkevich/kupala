import datetime
import sqlalchemy as sa
import typing
from sqlalchemy.orm import mapped_column

try:  # pragma: no cover
    from starlette_babel import timezone
except ImportError:  # pragma: no cover
    from datetime import datetime as timezone  # type: ignore[no-redef]

JsonList = typing.Annotated[list, mapped_column(sa.JSON, default=list, server_default="[]", nullable=False)]
JsonDict = typing.Annotated[dict, mapped_column(sa.JSON, default=dict, server_default="{}", nullable=False)]
IntPk = typing.Annotated[int, mapped_column(sa.BigInteger, primary_key=True)]
UuidPk = typing.Annotated[int, mapped_column(sa.UUID, primary_key=True)]
Slug = typing.Annotated[str, mapped_column(sa.Text, nullable=False)]
ShortString = typing.Annotated[str, mapped_column(sa.String(256), nullable=False, default="", server_default="")]
LongString = typing.Annotated[str, mapped_column(sa.String(512), nullable=False, default="", server_default="")]
Text = typing.Annotated[str, mapped_column(sa.Text(), nullable=False, default="", server_default="")]

AutoCreatedAt = typing.Annotated[
    datetime.datetime,
    mapped_column(
        sa.DateTime(True),
        default=timezone.now,
        server_default=sa.func.now(),
        nullable=False,
    ),
]
AutoUpdatedAt = typing.Annotated[
    datetime.datetime,
    mapped_column(
        sa.DateTime(True),
        default=timezone.now,
        server_default=sa.func.now(),
        server_onupdate=sa.func.now(),
        onupdate=timezone.now,
    ),
]
