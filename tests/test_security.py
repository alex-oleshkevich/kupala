import pytest
from passlib.handlers.pbkdf2 import pbkdf2_sha256

from kupala import security


def test_get_password_hasher() -> None:
    assert security.get_password_hasher(security.PasswordMethod.PBKDF2_SHA256) == pbkdf2_sha256


def test_generates_and_verifies_password_hash_using_default_method() -> None:
    password = "top!secret"
    password_hash = security.generate_password_hash(password)
    assert security.check_password_hash(password, password_hash)


@pytest.mark.asyncio
async def test_generates_and_verifies_password_hash_using_default_method_async() -> None:
    password = "top!secret"
    password_hash = await security.generate_password_hash_async(password)
    assert await security.check_password_hash_async(password, password_hash)
