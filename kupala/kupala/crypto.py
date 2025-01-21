from anyio.to_thread import run_sync
from cryptography.fernet import Fernet
from passlib.context import CryptContext


class Encryptor:
    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    async def aencrypt(self, data: bytes) -> bytes:
        return await run_sync(self.encrypt, data)

    def decrypt(self, data: bytes) -> bytes:
        return self._fernet.decrypt(data)

    async def adecrypt(self, data: bytes) -> bytes:
        return await run_sync(self.decrypt, data)


class Passwords:
    def __init__(self, schemes: list[str] | None = None) -> None:
        self.context = CryptContext(schemes=schemes or ["pbkdf2_sha256"])

    def make(self, plain_password: str) -> str:
        """Hash a plain password."""
        return self.context.hash(plain_password)

    async def amake(self, plain_password: str) -> str:
        """Hash a plain password."""
        return await run_sync(self.make, plain_password)

    def verify(self, hashed_password: str, plain_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        return self.context.verify(plain_password, hashed_password)

    async def averify(self, hashed_password: str, plain_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        return await run_sync(self.verify, hashed_password, plain_password)
