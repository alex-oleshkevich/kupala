import dataclasses

import typing


@dataclasses.dataclass
class Cookie:
    name: str
    value: str = ""
    path: str = "/"
    max_age: int | None = None
    expires: int | None = None
    domain: str | None = None
    secure: bool = False
    httponly: bool = False
    samesite: typing.Literal["lax", "strict", "none"] | None = "lax"
