from itsdangerous import (
    BadData,
    BadHeader,
    BadPayload,
    BadSignature,
    BadTimeSignature,
    TimestampSigner,
)
from itsdangerous import Signer as BaseSigner

from kupala.extensions import Extension

__all__ = [
    "Signer",
    "BadData",
    "BadHeader",
    "BadPayload",
    "BadSignature",
    "BadTimeSignature",
]


class Signer(BaseSigner, Extension):
    def __init__(self, secret_key: str | bytes) -> None:
        super().__init__(secret_key=secret_key)
        self.timed = TimestampSigner(secret_key=self.secret_key)
