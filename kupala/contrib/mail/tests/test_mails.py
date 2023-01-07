import jinja2
import pathlib
import pytest
from click.testing import CliRunner
from mailers import InMemoryTransport, Mailer
from starlette.applications import Starlette

from kupala.contrib.mail.commands import send_test_email_command
from kupala.contrib.mail.mails import Mails


@pytest.fixture
def transport() -> InMemoryTransport:
    return InMemoryTransport()


@pytest.fixture
def mailer(transport: InMemoryTransport) -> Mailer:
    return Mailer(transport, from_address="test@localhost")


@pytest.fixture
def templates_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path


@pytest.fixture
def jinja_env(templates_dir: pathlib.Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [
                jinja2.FileSystemLoader(templates_dir),
                jinja2.PackageLoader("kupala.contrib.mail"),
            ]
        )
    )


@pytest.mark.asyncio
async def test_sends_simple_mail(mailer: Mailer, transport: InMemoryTransport) -> None:
    mails = Mails({"default": mailer})
    await mails.send_mail(to="root@localhost", subject="hello", text="text", html="<span>html</span>")
    assert transport.mailbox
    message = transport.mailbox[0].as_string()
    assert "text" in message
    assert "<span>html</span>" in message


@pytest.mark.asyncio
async def test_sends_templated_mail(
    mailer: Mailer, transport: InMemoryTransport, jinja_env: jinja2.Environment, templates_dir: pathlib.Path
) -> None:
    (templates_dir / "text.html").write_text("text {{key}}")

    (templates_dir / "html.html").write_text(
        """
    {% extends 'kupala/mail/base_mail.html' %}
    {% block content %}<span>html {{key}}</span>{% endblock %}
    """
    )

    mails = Mails({"default": mailer}, jinja_env=jinja_env)
    await mails.send_templated_mail(
        to="root@localhost",
        subject="hello",
        text_template="text.html",
        html_template="html.html",
        context={"key": "value"},
    )
    assert transport.mailbox
    message = transport.mailbox[0].as_string()
    assert "text value" in message
    assert "<span>html value</span>" in message


def test_binds_to_starlette() -> None:
    app = Starlette()
    mails = Mails({})
    mails.setup(app)
    assert app.state.mail_ext == mails


def test_cli(mailer: Mailer, transport: InMemoryTransport) -> None:
    app = Starlette()
    mails = Mails({"default": mailer})
    mails.setup(app)

    runner = CliRunner()
    result = runner.invoke(send_test_email_command, ["me@localhost"], obj={"app": app})
    assert result.exit_code == 0
    assert result.output == "Message has been sent.\n"
    assert transport.mailbox
