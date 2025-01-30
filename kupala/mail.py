import typing
from email.message import EmailMessage

from mailers.encrypters import Encrypter
from mailers.exceptions import DeliveryError, MailersError, NotRegisteredTransportError
from mailers.factories import create_transport_from_url
from mailers.mailer import Mailer
from mailers.message import Email, Recipients
from mailers.preprocessors import Preprocessor
from mailers.preprocessors.cssliner import css_inliner
from mailers.preprocessors.remove_html_comments import remove_html_comments
from mailers.signers import Signer
from mailers.transports import (
    ConsoleTransport,
    FileTransport,
    InMemoryTransport,
    MultiTransport,
    NullTransport,
    StreamTransport,
    Transport,
)

from kupala import timezone
from kupala.extensions import Extension
from kupala.templating import Templates

__all__ = [
    "Mail",
    "Email",
    "EmailMessage",
    "Recipients",
    "css_inliner",
    "remove_html_comments",
    "Encrypter",
    "Mailer",
    "Signer",
    "Transport",
    "ConsoleTransport",
    "FileTransport",
    "InMemoryTransport",
    "StreamTransport",
    "NullTransport",
    "MultiTransport",
    "DeliveryError",
    "MailersError",
    "NotRegisteredTransportError",
    "create_transport_from_url",
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

        context = dict(context or {})
        context.update(self.template_context)
        context.update(
            {
                "preheader": preheader,
                "today": timezone.now(),
            },
        )

        text_content: str | None = self.templates.render(text_template, context) if text_template else None
        html_content: str | None = self.templates.render(html_template, context) if html_template else None
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
