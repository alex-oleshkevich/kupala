from __future__ import annotations

import functools
import typing

from anyio.to_thread import run_sync
from passlib.context import CryptContext

from kupala.extensions import Extension


class Passwords(Extension):
    def __init__(
        self,
        schemes: typing.Sequence[str] | None = None,
        default: str | None = None,
        deprecated: typing.Sequence[str] | typing.Literal["auto"] | None = None,
    ) -> None:
        self.context = CryptContext(
            schemes=schemes or ["pbkdf2_sha256"],
            default=default or "pbkdf2_sha256",
            deprecated=deprecated or "auto",
        )

    def make(self, plain_password: str, *, scheme: str | None = None) -> str:
        """Hash a plain password."""
        return self.context.hash(plain_password, scheme=scheme)

    def verify(
        self,
        plain_password: str,
        hashed_password: str,
        *,
        scheme: str | None = None,
    ) -> bool:
        """Verify a plain password against a hashed password."""
        return self.context.verify(plain_password, hashed_password, scheme=scheme)

    def verify_and_migrate(
        self,
        plain_password: str,
        hashed_password: str,
        *,
        scheme: str | None = None,
    ) -> tuple[bool, str]:
        """Verify password and re-hash the password if needed, all in a single call."""
        return self.context.verify_and_update(plain_password, hashed_password, scheme=scheme)

    def needs_update(self, hashed_password: str, *, scheme: str | None = None) -> bool:
        """Check if hash needs to be replaced for some reason,
        in which case the secret should be re-hashed."""
        return self.context.needs_update(hashed_password, scheme=scheme)

    async def amake(self, plain_password: str, *, scheme: str | None = None) -> str:
        """Hash a plain password."""
        return await run_sync(functools.partial(self.make, plain_password, scheme=scheme))

    async def averify(
        self,
        plain_password: str,
        hashed_password: str,
        *,
        scheme: str | None = None,
    ) -> bool:
        """Verify a plain password against a hashed password."""
        return await run_sync(functools.partial(self.verify, hashed_password, plain_password, scheme=scheme))

    async def averify_and_migrate(
        self,
        plain_password: str,
        hashed_password: str,
        *,
        scheme: str | None = None,
    ) -> tuple[bool, str]:
        """Verify password and re-hash the password if needed, all in a single call."""
        return await run_sync(
            functools.partial(
                self.verify_and_migrate,
                hashed_password,
                plain_password,
                scheme=scheme,
            )
        )
