from __future__ import annotations

import itsdangerous
import typing

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.application import Kupala


class Signer:
    def __init__(self, secret_key: str) -> None:
        self.signer = itsdangerous.signer.Signer(secret_key)
        self.timed_signer = itsdangerous.timed.TimestampSigner(secret_key)

    def sign(self, value: str | bytes) -> bytes:
        """Sign value."""
        return self.signer.sign(value)

    def unsign(self, signed_value: str | bytes) -> bytes:
        """
        Unsign value.

        Raises itsdangerous.BadSignature exception.
        """
        return self.signer.unsign(signed_value)

    def safe_unsign(self, signed_value: str | bytes) -> tuple[bool, typing.Optional[bytes]]:
        """
        Unsign value.

        Will not raise itsdangerous.BadSignature. Returns two-tuple: operation
        status and unsigned value.
        """
        try:
            return True, self.unsign(signed_value)
        except itsdangerous.BadSignature:
            return False, None

    def timed_sign(self, value: str | bytes) -> bytes:
        """
        Sign value.

        The signature will be valid for a specific time period.
        """
        return self.timed_signer.sign(value)

    def timed_unsign(self, signed_value: str | bytes, max_age: int) -> bytes:
        """
        Unsign value.

        Will raise itsdangerous.BadSignature or itsdangerous.BadTimeSignature
        exception if signed value cannot be decoded or expired..
        """
        return self.timed_signer.unsign(signed_value, max_age)

    def safe_timed_unsign(self, signed_value: str | bytes, max_age: int) -> tuple[bool, typing.Optional[bytes]]:
        """
        Unsign value.

        Will not raise itsdangerous.BadTimeSignature. Returns two-tuple:
        operation status and unsigned value.
        """
        try:
            return True, self.timed_unsign(signed_value, max_age)
        except itsdangerous.BadSignature:
            return False, None

    @classmethod
    def from_app(cls, app: Kupala) -> Signer:
        return app.state.signer
