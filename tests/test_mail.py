import jinja2
import pytest
from email.message import Message
from mailers import Email, InMemoryTransport, Mailer
from mailers.plugins.jinja_renderer import JinjaRendererPlugin
from pathlib import Path

from kupala.mails import send_mail, send_templated_mail


@pytest.mark.asyncio
async def test_mail_regular_send() -> None:
    storage: list[Message] = []
    mailer = Mailer(InMemoryTransport(storage), from_address="root <root@localhost>")
    await send_mail(mailer, Email(subject="test", text="body"))
    assert len(storage) == 1
    assert storage[0]["From"] == "root <root@localhost>"


@pytest.mark.asyncio
async def test_send_templated_mail(jinja_template_path: Path, jinja_env: jinja2.Environment) -> None:
    with open(jinja_template_path / "index.html", "w") as f:
        f.write("base mail")

    storage: list[Message] = []
    mailer = Mailer(
        InMemoryTransport(storage),
        from_address="root <root@localhost>",
        plugins=[JinjaRendererPlugin(jinja_env)],
    )
    await send_templated_mail(mailer, to="root@localhost", subject="test", html_template="index.html")
    assert len(storage) == 1
    assert storage[0]["From"] == "root <root@localhost>"
    assert storage[0].get_payload() == "base mail\n"
