from __future__ import annotations

import typing
from mailers import Email, Mailer, Plugin, SentMessages, TemplatedEmail
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


async def send_mail(
    mailer: Mailer,
    message: Email | None = None,
    *,
    to: Recipients | None = None,
    subject: str | None = None,
    from_address: Recipients | None = None,
    cc: Recipients | None = None,
    bcc: Recipients | None = None,
    reply_to: Recipients | None = None,
    headers: dict[str, str] | None = None,
    sender: str | None = None,
    html: str | None = None,
    text: str | None = None,
    return_path: str | None = None,
    text_charset: str = "utf-8",
    html_charset: str = "utf-8",
    boundary: str | None = None,
    message_id: str | None = None,
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
    message: Email | None = None,
    *,
    to: Recipients | None = None,
    subject: str | None = None,
    from_address: Recipients | None = None,
    cc: Recipients | None = None,
    bcc: Recipients | None = None,
    reply_to: Recipients | None = None,
    headers: dict[str, str] | None = None,
    sender: str | None = None,
    html_template: str | None = None,
    text_template: str | None = None,
    context: dict[str, typing.Any] | None = None,
    return_path: str | None = None,
    text_charset: str | None = "utf-8",
    html_charset: str | None = "utf-8",
    boundary: str | None = None,
    message_id: str | None = None,
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
