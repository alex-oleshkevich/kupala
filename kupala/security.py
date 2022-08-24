import enum
from passlib.hash import pbkdf2_sha256, pbkdf2_sha512, sha256_crypt, sha512_crypt
from passlib.ifc import PasswordHash
from starlette.concurrency import run_in_threadpool


class PasswordMethod(str, enum.Enum):
    PBKDF2_SHA256 = ("pbkdf2_sha256",)
    PBKDF2_SHA512 = ("pbkdf2_sha512",)
    SHA256_CRYPT = ("sha256_crypt",)
    SHA512_CRYPT = ("sha512_crypt",)


HASHERS = {
    PasswordMethod.PBKDF2_SHA256: pbkdf2_sha256,
    PasswordMethod.PBKDF2_SHA512: pbkdf2_sha512,
    PasswordMethod.SHA256_CRYPT: sha256_crypt,
    PasswordMethod.SHA512_CRYPT: sha512_crypt,
}

DEFAULT_METHOD = PasswordMethod.PBKDF2_SHA256


def get_password_hasher(method: PasswordMethod) -> PasswordHash:
    """Get registered password hasher by name."""
    return HASHERS.get(method)


def generate_password_hash(password: str, method: PasswordMethod = DEFAULT_METHOD) -> str:
    """Hash given password using selected hashing method."""
    return get_password_hasher(method).hash(password)


async def generate_password_hash_async(password: str, method: PasswordMethod = DEFAULT_METHOD) -> str:
    """
    Hash given password using selected hashing method.

    The hash function will be executed in threadpool.
    """
    return await run_in_threadpool(generate_password_hash, password, method)


def check_password_hash(plain_password: str, hashed_password: str, method: PasswordMethod = DEFAULT_METHOD) -> bool:
    """Verify given password hash using selected hashing method."""
    return get_password_hasher(method).verify(plain_password, hashed_password)


async def check_password_hash_async(plain_password: str, hashed_password: str) -> bool:
    """
    Verify given password hash using selected hashing method.

    The hash function will be executed in threadpool.
    """
    return await run_in_threadpool(check_password_hash, plain_password, hashed_password)
