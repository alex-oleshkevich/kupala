import itsdangerous
import pytest

from kupala.security.signing import (
    safe_timed_unsign_value,
    safe_unsign_value,
    sign_value,
    timed_sign_value,
    timed_unsign_value,
    unsign_value,
)


@pytest.fixture()
def secret_key() -> str:
    return "key!"


def test_signer(secret_key: str) -> None:
    value = "value"
    signed_value = sign_value(secret_key, value)
    assert unsign_value(secret_key, signed_value) == value.encode()


def test_signer_raises(secret_key: str) -> None:
    value = "value"
    with pytest.raises(itsdangerous.BadSignature):
        unsign_value(secret_key, value)


def test_signer_safe_unsign_ok(secret_key: str) -> None:
    signed_value = sign_value(secret_key, "value")
    ok, value = safe_unsign_value(secret_key, signed_value)
    assert ok is True
    assert value == b"value"


def test_signer_safe_unsign_fail(secret_key: str) -> None:
    ok, value = safe_unsign_value(secret_key, "value")
    assert ok is False
    assert value is None


def test_timed_signer(secret_key: str) -> None:
    value = "value"
    signed_value = timed_sign_value(secret_key, value)
    assert timed_unsign_value(secret_key, signed_value, 10) == value.encode()


def test_timed_signer_raises_for_invalid_value(secret_key: str) -> None:
    value = "value"
    with pytest.raises(itsdangerous.BadSignature):
        timed_unsign_value(secret_key, value, 10)


def test_signer_safe_timed_unsign_ok(secret_key: str) -> None:
    signed_value = timed_sign_value(secret_key, "value")
    ok, value = safe_timed_unsign_value(secret_key, signed_value, 10)
    assert ok is True
    assert value == b"value"


def test_signer_safe_timed_unsign_fail(secret_key: str) -> None:
    ok, value = safe_timed_unsign_value(secret_key, "value", 10)
    assert ok is False
    assert value is None
