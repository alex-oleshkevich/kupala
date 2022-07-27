from __future__ import annotations

from email.message import Message
from mailers import Email, Encrypter, Mailer, Plugin, SentMessages, Signer, TemplatedEmail, create_transport_from_url
from mailers.message import Recipients

try:
    import toronado
except ImportError:
    toronado = None


class CSSInlinerPlugin(Plugin):
    def __init__(self) -> None:
        assert toronado, 'CSSInlinerPlugin depends on "toronado" package.'

    def process_email(self, email: Email) -> Email:
        if email.html:
            email.html = toronado.from_string(email.html).decode()
        return email


class MailerManager:
    def __init__(self, mailers: dict[str, Mailer] | None = None, default: str = 'default') -> None:
        self._mailers = mailers or {}
        self._default = default

    @property
    def default(self) -> Mailer:
        """Get default mailer."""
        return self.get(self._default)

    def use(
        self,
        url: str,
        *,
        from_address: str = 'no-reply@example.com',
        from_name: str = 'Example',
        signer: Signer = None,
        encrypter: Encrypter = None,
        plugins: list[Plugin] = None,
        name: str = 'default',
    ) -> MailerManager:
        """Create and configure mailer from URL."""
        if from_name:
            from_address = f'{from_name} <{from_address}>'
        transport = create_transport_from_url(url)
        return self.add(
            name,
            Mailer(
                transport,
                from_address=from_address,
                plugins=plugins,
                signer=signer,
                encrypter=encrypter,
            ),
        )

    def add(self, name: str, mailer: Mailer) -> MailerManager:
        """Add new mailer."""
        assert name not in self._mailers, f'"{name}" already exists.'
        self._mailers[name] = mailer
        return self

    def get(self, name: str) -> Mailer:
        """Get mailer by name."""
        if name not in self._mailers:
            raise KeyError(f'No mailer named "{name}" defined.')
        return self._mailers[name]

    async def send(self, message: Email | Message, name: str = 'default') -> SentMessages:
        """Send message using selected mailer."""
        mailer = self.get(name)
        return await mailer.send(message)

    def set_default(self, name: str) -> MailerManager:
        """Set default mailer name."""
        self._default = name
        return self


async def send_mail(
    mailer: Mailer,
    message: Email = None,
    *,
    to: Recipients = None,
    subject: str = None,
    from_address: Recipients = None,
    cc: Recipients = None,
    bcc: Recipients = None,
    reply_to: Recipients = None,
    headers: dict = None,
    sender: str = None,
    html: str = None,
    text: str = None,
    return_path: str = None,
    text_charset: str = 'utf-8',
    html_charset: str = 'utf-8',
    boundary: str = None,
    message_id: str = None,
) -> SentMessages:
    message = message or Email(
        to=to,
        subject=subject,
        from_address=from_address,
        cc=cc,
        bcc=bcc,
        reply_to=reply_to,
        headers=headers,
        sender=sender,
        text=text,
        html=html,
        return_path=return_path,
        text_charset=text_charset,
        html_charset=html_charset,
        boundary=boundary,
        message_id=message_id,
    )
    return await mailer.send(message)


async def send_templated_mail(
    mailer: Mailer,
    message: Email = None,
    *,
    to: Recipients = None,
    subject: str = None,
    from_address: Recipients = None,
    cc: Recipients = None,
    bcc: Recipients = None,
    reply_to: Recipients = None,
    headers: dict = None,
    sender: str = None,
    html_template: str = None,
    text_template: str = None,
    context: dict = None,
    return_path: str = None,
    text_charset: str = 'utf-8',
    html_charset: str = 'utf-8',
    boundary: str = None,
    message_id: str = None,
) -> SentMessages:
    message = message or TemplatedEmail(
        to=to,
        subject=subject,
        from_address=from_address,
        cc=cc,
        bcc=bcc,
        reply_to=reply_to,
        headers=headers,
        sender=sender,
        html_template=html_template,
        text_template=text_template,
        context=context,
        return_path=return_path,
        text_charset=text_charset,
        html_charset=html_charset,
        boundary=boundary,
        message_id=message_id,
    )

    return await mailer.send(message)
