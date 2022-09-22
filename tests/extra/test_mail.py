import jinja2
import os
import pytest
from email.message import Message
from mailers import Email, InMemoryTransport, Mailer
from mailers.plugins.jinja_renderer import JinjaRendererPlugin

from kupala.extra.mails import send_mail, send_templated_mail


@pytest.mark.asyncio
async def test_mail_regular_send() -> None:
    storage: list[Message] = []
    mailer = Mailer(InMemoryTransport(storage), from_address="root <root@localhost>")
    await send_mail(mailer, Email(subject="test", text="body"))
    assert len(storage) == 1
    assert storage[0]["From"] == "root <root@localhost>"


@pytest.mark.asyncio
async def test_send_templated_mail(tmp_path: os.PathLike) -> None:
    jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader([tmp_path]))
    with open(os.path.join(tmp_path, "index.html"), "w") as f:
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
