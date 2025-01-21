import base64
import secrets

import pytest

from kupala.crypto import Encryptor, Passwords


@pytest.fixture
def passwords() -> Passwords:
    return Passwords()


@pytest.fixture
def encryptor() -> Encryptor:
    key = base64.encodebytes(secrets.token_bytes(32))
    return Encryptor(key)


class TestPasswords:
    def test_password_verification(self, passwords: Passwords) -> None:
        plain_password = "password"
        hashed_password = passwords.make(plain_password)
        assert passwords.verify(hashed_password, plain_password)

    async def test_password_async_verification(self, passwords: Passwords) -> None:
        plain_password = "password"
        hashed_password = await passwords.amake(plain_password)
        assert await passwords.averify(hashed_password, plain_password)

    def test_password_migration(self) -> None:
        plain_password = "password"

        passwords_sha256 = Passwords(["pbkdf2_sha256"])
        passwords_sha512 = Passwords(["pbkdf2_sha512"])
        hashed_password_sha512 = passwords_sha512.make(plain_password)
        hashed_password_sha256 = passwords_sha256.make(plain_password)

        passwords = Passwords(["pbkdf2_sha256", "pbkdf2_sha512"])
        assert passwords.verify(hashed_password_sha512, plain_password)
        assert passwords.verify(hashed_password_sha256, plain_password)


class TestEncryptor:
    def test_encryption(self, encryptor: Encryptor) -> None:
        data = b"hello, world!"
        encrypted = encryptor.encrypt(data)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == data

    async def test_encryption_async(self, encryptor: Encryptor) -> None:
        data = b"hello, world!"
        encrypted = await encryptor.aencrypt(data)
        decrypted = await encryptor.adecrypt(encrypted)
        assert decrypted == data
