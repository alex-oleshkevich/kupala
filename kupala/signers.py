import typing
import click
from itsdangerous import (
    BadData,
    BadHeader,
    BadPayload,
    BadSignature,
    BadTimeSignature,
    TimestampSigner,
)
from itsdangerous import Signer as BaseSigner
from starlette_dispatch import VariableResolver

from kupala.applications import AppConfig, Kupala

__all__ = [
    "Signer",
    "BadData",
    "BadHeader",
    "BadPayload",
    "BadSignature",
    "BadTimeSignature",
]


class Signer(BaseSigner):
    def __init__(self, secret_key: str | bytes) -> None:
        super().__init__(secret_key=secret_key)
        self.timed = TimestampSigner(secret_key=self.secret_key)

    def timed_sign(self, value: str) -> str:
        return self.timed.sign(value)

    def timed_unsign(self, value: str, max_age: int) -> str:
        return self.timed.unsign(value, max_age=max_age)

    def configure_application(self, app_config: AppConfig) -> None:
        app_config.state["signer"] = self
        app_config.commands.append(signer_command)
        app_config.dependency_resolvers[type(self)] = VariableResolver(self)

    @classmethod
    def of(cls, app: Kupala) -> typing.Self:
        return app.state.signer


signer_command = click.Group("signer", help="Data signing.")


@signer_command.command("sign")
@click.option("--timed", is_flag=True, help="Use timed signature.")
@click.argument("data")
@click.pass_obj
def sign_command(app: Kupala, timed: bool, data: str) -> None:
    """Sign plain text."""
    encryptor = Signer.of(app)
    if timed:
        click.echo(encryptor.timed_sign(data))
    else:
        click.echo(encryptor.sign(data))


@signer_command.command("unsign")
@click.option("--max-age", type=int, help="Maximum age of the timed signature, in seconds.")
@click.argument("data")
@click.pass_obj
def decrypt_command(app: Kupala, data: str, max_age: int) -> None:
    """Verify signature and print plain text."""
    signer = Signer.of(app)
    try:
        if max_age:
            click.echo(signer.timed_unsign(data, max_age))
        else:
            click.echo(signer.unsign(data))
    except BadSignature as exc:
        raise click.ClickException(str(exc))
