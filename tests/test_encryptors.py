import base64
import secrets

import pytest

from kupala.encryptors import Encryptor


@pytest.fixture
def encryptor() -> Encryptor:
    key = base64.encodebytes(secrets.token_bytes(32))
    return Encryptor(key)


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
