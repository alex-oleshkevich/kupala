from __future__ import annotations

import itsdangerous
import typing


def sign_value(secret_key: str, value: str | bytes) -> bytes:
    """Sign value."""
    return itsdangerous.signer.Signer(secret_key).sign(value)


def unsign_value(secret_key: str, signed_value: str | bytes) -> bytes:
    """
    Unsign value.

    Raises itsdangerous.BadSignature exception.
    """
    return itsdangerous.signer.Signer(secret_key).unsign(signed_value)


def safe_unsign_value(secret_key: str, signed_value: str | bytes) -> tuple[bool, typing.Optional[bytes]]:
    """
    Safely unsign value.

    Will not raise itsdangerous.BadSignature. Returns two-tuple: operation
    status and unsigned value.
    """
    try:
        return True, unsign_value(secret_key, signed_value)
    except itsdangerous.BadSignature:
        return False, None


def timed_sign_value(secret_key: str, value: str | bytes) -> bytes:
    """
    Sign value.

    The signature will be valid for a specific time period.
    """
    return itsdangerous.TimestampSigner(secret_key).sign(value)


def timed_unsign_value(secret_key: str, signed_value: str | bytes, max_age: int) -> bytes:
    """
    Unsign value.

    Will raise itsdangerous.BadSignature or itsdangerous.BadTimeSignature
    exception if signed value cannot be decoded or expired..
    """
    return itsdangerous.TimestampSigner(secret_key).unsign(signed_value, max_age)


def safe_timed_unsign_value(
    secret_key: str, signed_value: str | bytes, max_age: int
) -> tuple[bool, typing.Optional[bytes]]:
    """
    Safely unsign value.

    Will not raise itsdangerous.BadTimeSignature. Returns two-tuple: operation
    status and unsigned value.
    """
    try:
        return True, timed_unsign_value(secret_key, signed_value, max_age)
    except itsdangerous.BadSignature:
        return False, None
