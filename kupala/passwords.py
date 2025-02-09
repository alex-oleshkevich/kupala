from __future__ import annotations

import functools
import typing

from anyio.to_thread import run_sync
import click
from passlib.context import CryptContext
from starlette_dispatch import VariableResolver

from kupala.applications import AppConfig, Kupala


class Passwords:
    def __init__(
        self,
        schemes: typing.Sequence[str] | None = None,
        default: str | None = None,
        deprecated: typing.Sequence[str] | typing.Literal["auto"] | None = None,
    ) -> None:
        schemes = schemes or ["pbkdf2_sha256"]
        self.context = CryptContext(
            schemes=schemes,
            default=default or schemes[0],
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
        return await run_sync(functools.partial(self.verify, plain_password, hashed_password, scheme=scheme))

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
                plain_password,
                hashed_password,
                scheme=scheme,
            )
        )

    def configure_application(self, app_config: AppConfig) -> None:
        app_config.state["passwords"] = self
        app_config.commands.append(passwords_command)
        app_config.dependency_resolvers[type(self)] = VariableResolver(self)

    @classmethod
    def of(cls, app: Kupala) -> typing.Self:
        return app.state.passwords


passwords_command = click.Group("passwords")


@passwords_command.command("hash")
@click.argument("password")
@click.pass_obj
def hash_password_command(app: Kupala, password: str) -> None:
    """Hash a password."""
    passwords = Passwords.of(app)
    click.echo(passwords.make(password))


@passwords_command.command("verify")
@click.argument("hashed_password")
@click.argument("plain_password")
@click.pass_obj
def verify_password_command(app: Kupala, hashed_password: str, plain_password: str) -> None:
    """Verify a password."""
    passwords = Passwords.of(app)
    valid, new_hash = passwords.verify_and_migrate(plain_password, hashed_password)
    click.echo(
        "Valid: {valid}".format(valid=click.style("yes", fg="green") if valid else click.style("no", fg="yellow"))
    )
    if valid:
        click.echo(
            "Needs migration: {value}".format(
                value=click.style("yes", fg="yellow") if new_hash else click.style("no", fg="green")
            )
        )
