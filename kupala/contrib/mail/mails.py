from __future__ import annotations

import contextlib
import jinja2
import typing
from mailers import Mailer
from mailers.message import Email, Recipients
from starlette.applications import Starlette

from kupala.applications import Kupala


class Mails:
    def __init__(self, mailers: dict[str, Mailer], jinja_env: jinja2.Environment | None = None) -> None:
        self.mailers = mailers
        self.jinja_env = jinja_env

    async def send_mail(
        self,
        message: Email | None = None,
        *,
        to: Recipients | None = None,
        subject: str | None = None,
        html: str | None = None,
        text: str | None = None,
        from_address: Recipients | None = None,
        mailer: str = "default",
    ) -> None:
        message = message or Email(to=to, subject=str(subject or ""), from_address=from_address, text=text, html=html)
        return await self.get_mailer(mailer).send(message)

    async def send_templated_mail(
        self,
        to: Recipients,
        subject: str,
        html_template: str | None = None,
        text_template: str | None = None,
        from_address: Recipients | None = None,
        context: dict[str, typing.Any] | None = None,
        mailer: str = "default",
    ) -> None:
        assert self.jinja_env
        text_content: str | None = self.jinja_env.get_template(text_template).render(context) if text_template else None
        html_content: str | None = self.jinja_env.get_template(html_template).render(context) if html_template else None
        await self.send_mail(
            to=to,
            subject=subject,
            from_address=from_address,
            text=text_content,
            html=html_content,
            mailer=mailer,
        )

    def get_mailer(self, name: str) -> Mailer:
        return self.mailers[name]

    def setup(self, app: Starlette) -> None:
        app.state.mail_ext = self

    @contextlib.asynccontextmanager
    async def bootstrap(self, app: Kupala) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
        from kupala.contrib.mail.commands import mail_commands

        app.cli.add_command(mail_commands)
        yield {"mail": self}
