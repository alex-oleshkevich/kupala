from __future__ import annotations

import typing as t
from contextlib import contextmanager

from mailers import Attachment, EmailMessage, get_mailer

from kupala.helpers import config, render_template


class MailComposer:
    def __init__(
        self,
        subject: str = None,
        text_body: str = None,
        html_body: str = None,
        from_address: str = None,
        cc: str = None,
        bcc: str = None,
        reply_to: str = None,
        headers: str = None,
        charset: str = None,
    ):
        self._message = EmailMessage(
            cc=cc,
            bcc=bcc,
            subject=subject,
            charset=charset,
            headers=headers,
            reply_to=reply_to,
            text_body=text_body,
            html_body=html_body,
            from_address=from_address,
        )

    def text_body(self, body: str) -> MailComposer:
        self._message.text_body = body
        return self

    def use_text_template(self, template: str, context: dict = None) -> MailComposer:
        self._message.text_body = render_template(template, context)
        return self

    def html_body(self, body: str) -> MailComposer:
        self._message.html_body = body
        return self

    def use_html_template(self, template: str, context: dict = None) -> MailComposer:
        self._message.html_body = render_template(template, context)
        return self

    def use_templates(
        self, html_template: str = None, text_template: str = None, context: dict = None
    ) -> MailComposer:
        if html_template:
            self.use_html_template(html_template, context)
        if text_template:
            self.use_text_template(text_template, context)
        return self

    def from_address(self, address: str) -> MailComposer:
        self._message.from_address = address
        return self

    def subject(self, subject: str) -> MailComposer:
        self._message.subject = subject
        return self

    def to(self, address: str, name: str = None) -> MailComposer:
        self._message.add_to(address, name)
        return self

    def cc(self, address: str, name: str = None) -> MailComposer:
        self._message.add_cc(address, name)
        return self

    def bcc(self, address: str, name: str = None) -> MailComposer:
        self._message.add_bcc(address, name)
        return self

    def reply_to(self, address: str, name: str) -> MailComposer:
        self._message.add_reply_to(address, name)
        return self

    def header(self, name: str, value: str) -> MailComposer:
        self._message.headers[name] = value
        return self

    def charset(self, charset: str) -> MailComposer:
        self._message.charset = charset
        return self

    def attach(
        self,
        contents: t.AnyStr,
        file_name: str,
        mime_type: str = "application/octet-stream",
    ) -> MailComposer:
        self._message.attach(contents, file_name, mime_type)
        return self

    def add_attachment(self, attachment: Attachment) -> MailComposer:
        self._message.add_attachment(attachment)
        return self

    async def send(self, mailer: str = "default") -> None:
        if not self._message.from_address:
            self._message.from_address = config("mailers.from_address")
        await get_mailer(mailer).send(self._message)


@contextmanager
def compose(**kwargs: t.Any) -> t.Iterator[MailComposer]:
    yield MailComposer(**kwargs)
