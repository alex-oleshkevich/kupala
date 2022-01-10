from mailers import Email, Plugin, SentMessages, TemplatedEmail
from mailers.message import Recipients

from kupala.application import get_current_application

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

    app = get_current_application()
    return await app.mail.send(message)


async def send_templated_mail(
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

    app = get_current_application()
    return await app.mail.send(message)
