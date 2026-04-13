from email.message import EmailMessage

import jinja2
import pytest
from mailers import InMemoryTransport
from mailers.pytest_plugin import Mailbox

from kupala.mail import Mail
from kupala.templating import Templates


@pytest.fixture
def mail() -> Mail:
    return Mail(dsn="memory://", from_address="root@localhost", from_name="Root")


@pytest.fixture
def mailbox(mail: Mail) -> list[EmailMessage]:
    assert isinstance(mail.transport, InMemoryTransport)
    return mail.transport.mailbox


async def test_from_address(mail: Mail, mailbox: Mailbox) -> None:
    await mail.send_mail(to="me@me.com", subject="Test", text="Test body")
    assert mailbox[0]["from"] == "Root <root@localhost>"


async def test_send_mail(mail: Mail, mailbox: Mailbox) -> None:
    await mail.send_mail(to="me@me.com", subject="Test", text="Test body")
    assert mailbox[0]["to"] == "me@me.com"
    assert mailbox[0]["subject"] == "Test"
    assert mailbox[0].get_content() == "Test body\n"


async def test_send_templated_mail() -> None:
    mail = Mail(
        dsn="memory://",
        from_address="root@localhost",
        from_name="Root",
        templates=Templates(
            jinja_env=jinja2.Environment(
                autoescape=True,
                loader=jinja2.DictLoader(
                    {
                        "text.txt": "Test body",
                        "text.html": "<b>Test body</b>",
                    }
                ),
            ),
        ),
    )

    await mail.send_templated_mail(
        to="me@me.com",
        subject="Test",
        text_template="text.txt",
        html_template="text.html",
    )

    assert isinstance(mail.transport, InMemoryTransport)
    mailbox = mail.transport.mailbox
    assert len(mailbox) == 1
    assert mailbox[0]["to"] == "me@me.com"
    assert mailbox[0]["subject"] == "Test"
    assert mailbox[0].get_payload(0).get_content() == "Test body\n"  # type: ignore[union-attr]
    assert mailbox[0].get_payload(1).get_content() == "<b>Test body</b>\n"  # type: ignore[union-attr]
