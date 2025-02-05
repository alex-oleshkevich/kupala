import typing
from email.message import EmailMessage

import anyio
import click
from mailers.encrypters import Encrypter
from mailers.mailer import Mailer
from mailers.message import Email, Recipients
from mailers.preprocessors import Preprocessor
from mailers.preprocessors.cssliner import css_inliner
from mailers.preprocessors.remove_html_comments import remove_html_comments
from mailers.signers import Signer
from mailers.transports import (
    ConsoleTransport,
    InMemoryTransport,
    MultiTransport,
    NullTransport,
    StreamTransport,
    Transport,
)
from mailers.transports.smtp import SMTPTransport

from kupala import timezone
from kupala.applications import Kupala
from kupala.extensions import Extension
from kupala.templating import Templates

__all__ = [
    "Mail",
    "Email",
    "EmailMessage",
    "Recipients",
    "mail_command",
    "Signer",
    "Encrypter",
    "Preprocessor",
    "Transport",
    "css_inliner",
    "remove_html_comments",
    "ConsoleTransport",
    "SMTPTransport",
    "InMemoryTransport",
    "MultiTransport",
    "NullTransport",
    "StreamTransport",
]


class Mail(Extension):
    """Mail extension for sending emails."""

    def __init__(
        self,
        mailer: Mailer | None = None,
        *,
        dsn: str | None = None,
        from_name: str,
        from_address: str,
        signer: typing.Optional[Signer] = None,
        encrypter: typing.Optional[Encrypter] = None,
        preprocessors: typing.Sequence[Preprocessor] = [],
        template_context: typing.Mapping[str, typing.Any] | None = None,
        templates: Templates | None = None,
    ) -> None:
        if mailer is None and dsn is None:
            raise ValueError("Either mailer or DSN must be provided.")

        if mailer is None:
            assert dsn is not None, "DSN must be provided."
            from_address = f"{from_name} <{from_address}>"
            mailer = Mailer(dsn, from_address, signer, encrypter, list(preprocessors))

        self.mailer = mailer
        self.templates = templates
        self.template_context = dict(template_context or {})

    def install(self, app: Kupala):
        super().install(app)
        app.commands.append(mail_command)

    @property
    def transport(self) -> Transport:
        """Get underlying transport instance."""
        return self.mailer.transport

    async def send(self, message: typing.Union[Email, EmailMessage]) -> None:
        """Send a pre-built email message."""
        return await self.mailer.send(message)

    async def send_mail(
        self,
        to: Recipients | None = None,
        subject: str | None = None,
        *,
        cc: Recipients | None = None,
        bcc: Recipients | None = None,
        html: str | None = None,
        text: str | None = None,
        from_address: Recipients | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send an email message to one or more recipients."""
        return await self.mailer.send(
            Email(
                to=to,
                cc=cc,
                bcc=bcc,
                subject=str(subject or ""),
                from_address=from_address,
                text=text,
                html=html,
                headers=headers,
            )
        )

    async def send_templated_mail(
        self,
        to: str,
        subject: str,
        *,
        cc: Recipients | None = None,
        bcc: Recipients | None = None,
        text_template: str | None = None,
        html_template: str | None = None,
        context: typing.Mapping[str, typing.Any] | None = None,
        from_address: Recipients | None = None,
        headers: dict[str, str] | None = None,
        preheader: str = "",
    ) -> None:
        """Send an email message to one or more recipients.

        Text or HTML body are rendered from the templates."""
        assert self.templates, "Templates are not configured for use with mailer."

        template_context = {}
        template_context.update(self.template_context)
        template_context.update(context or {})
        template_context.update(
            {
                "preheader": preheader,
                "today": timezone.now(),
            },
        )

        text_content: str | None = self.templates.render(text_template, template_context) if text_template else None
        html_content: str | None = self.templates.render(html_template, template_context) if html_template else None
        await self.send_mail(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            html=html_content,
            text=text_content,
            from_address=from_address,
            headers=headers,
        )


mail_command = click.Group(name="mail", help="Mail commands.")


@mail_command.command("send-test")
@click.argument("recipient")
@click.option("--subject", default="Test email")
@click.option("--body", default="This is a test email.")
@click.option("--html", default=False, is_flag=True)
def send_test_mail_command(recipient: str, subject: str, body: str, html: bool) -> None:
    """Send a test email."""

    async def main() -> None:
        mailer = Mail.of(Kupala.current())

        if not html:
            await mailer.send_mail(to=recipient, subject=subject, text=body)
            return

        await mailer.send_templated_mail(
            to=recipient,
            subject=subject,
            text_template="kupala/mail/test_message.txt",
            html_template="kupala/mail/test_message.html",
            context={"body": body},
        )

    anyio.run(main)
