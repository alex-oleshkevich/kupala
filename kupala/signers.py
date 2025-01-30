from itsdangerous import (
    BadData,
    BadHeader,
    BadPayload,
    BadSignature,
    BadTimeSignature,
)
from itsdangerous import (
    Signer as BaseSigner,
)
from itsdangerous import (
    TimestampSigner as BaseTimestampSigner,
)

from kupala.extensions import Extension

__all__ = [
    "Signer",
    "TimestampSigner",
    "BadData",
    "BadHeader",
    "BadPayload",
    "BadSignature",
    "BadTimeSignature",
]


class Signer(BaseSigner, Extension): ...


class TimestampSigner(BaseTimestampSigner, Extension): ...
