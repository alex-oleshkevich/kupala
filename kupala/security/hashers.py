import abc
import typing as t

from passlib import hash
from passlib.ifc import PasswordHash


class BaseHasher(abc.ABC):  # pragma: nocover
    algorithm: t.Any = None

    def get_algorithm(self) -> PasswordHash:
        if self.algorithm is not None:
            return self.algorithm
        raise NotImplementedError()

    def hash(self, plain: str) -> str:
        return self.get_algorithm().hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        return self.get_algorithm().verify(plain, hashed)

    def needs_update(self, hashed: str) -> bool:
        return self.get_algorithm().needs_update(hashed)


class Pbkdf2Sha256Hasher(BaseHasher):
    algorithm = hash.pbkdf2_sha256


class Pbkdf2Sha512Hasher(BaseHasher):
    algorithm = hash.pbkdf2_sha512


class InsecureHasher(BaseHasher):
    def hash(self, plain: str) -> str:
        return plain

    def verify(self, plain: str, hashed: str) -> bool:
        return plain == hashed

    def needs_update(self, hashed: str) -> bool:
        return False
