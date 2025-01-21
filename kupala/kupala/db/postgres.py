import typing

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

type JSONSerializable = str | int | float | bool | None | dict[str, JSONSerializable] | list[JSONSerializable]

JSONDict = typing.Annotated[dict[str, JSONSerializable], mapped_column(JSONB, default=dict, server_default="{}")]
JSONList = typing.Annotated[list[JSONSerializable], mapped_column(JSONB, default=list, server_default="[]")]
