from __future__ import annotations

from anyio.to_thread import run_sync
from cryptography.fernet import Fernet

from kupala.extensions import Extension


class Encryptor(Extension):
    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._fernet.decrypt(data)

    async def aencrypt(self, data: bytes) -> bytes:
        return await run_sync(self.encrypt, data)

    async def adecrypt(self, data: bytes) -> bytes:
        return await run_sync(self.decrypt, data)
