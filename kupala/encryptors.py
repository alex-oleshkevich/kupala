from __future__ import annotations

import typing

import click
from anyio.to_thread import run_sync
from cryptography.fernet import Fernet
from starlette_dispatch import VariableResolver

from kupala.applications import AppConfig, Kupala


class Encryptor:
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

    def configure_application(self, app_config: AppConfig) -> None:
        app_config.state["encryptor"] = self
        app_config.commands.append(encryptor_command)
        app_config.dependency_resolvers[type(self)] = VariableResolver(self)

    @classmethod
    def of(cls, app: Kupala) -> typing.Self:
        return app.state.encryptor


encryptor_command = click.Group("encryptor", help="Encryptor commands")


@encryptor_command.command("encrypt")
@click.argument("data")
@click.pass_obj
def encrypt_command(app: Kupala, data: str) -> None:
    """Encrypt plain text."""
    encryptor = Encryptor.of(app)
    click.echo(encryptor.encrypt(data.encode()).decode())


@encryptor_command.command("decrypt")
@click.argument("data")
@click.pass_obj
def decrypt_command(app: Kupala, data: str) -> None:
    """Decrypt encrypted string back to plain text."""
    encryptor = Encryptor.of(app)
    click.echo(encryptor.decrypt(data.encode()).decode())
