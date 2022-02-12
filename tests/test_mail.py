import pytest
from email.message import Message
from mailers import Email, InMemoryTransport, Mailer
from mailers.plugins.jinja_renderer import JinjaRendererPlugin
from pathlib import Path

from kupala.application import Kupala
from kupala.mails import send_mail, send_templated_mail


@pytest.mark.asyncio
async def test_mail_regular_send() -> None:
    storage: list[Message] = []
    app = Kupala()
    mailer = Mailer(InMemoryTransport(storage), from_address='root <root@localhost>')
    app.mail.add('default', mailer)
    await send_mail(mailer, Email(subject='test', text='body'))
    assert len(storage) == 1
    assert storage[0]['From'] == 'root <root@localhost>'


@pytest.mark.asyncio
async def test_send_templated_mail(tmpdir: Path) -> None:
    with open(tmpdir / 'index.html', 'w') as f:
        f.write('base mail')

    storage: list[Message] = []
    app = Kupala(template_dir=tmpdir)
    mailer = Mailer(
        InMemoryTransport(storage),
        from_address='root <root@localhost>',
        plugins=[JinjaRendererPlugin(app.state.jinja_env)],
    )
    app.mail.add('default', mailer)
    await send_templated_mail(mailer, to='root@localhost', subject='test', html_template='index.html')
    assert len(storage) == 1
    assert storage[0]['From'] == 'root <root@localhost>'
    assert storage[0].get_payload() == 'base mail\n'


def test_mail_use() -> None:
    app = Kupala()
    app.mail.use('memory://')
    assert isinstance(app.mail.get_default(), Mailer)

    with pytest.raises(KeyError, match='No mailer named'):
        app.mail.get('missing')


def test_mail_add() -> None:
    storage: list[Message] = []
    app = Kupala()
    app.mail.add('default', Mailer(InMemoryTransport(storage)))
    assert isinstance(app.mail.get_default(), Mailer)


@pytest.mark.asyncio
async def test_mail_send() -> None:
    storage: list[Message] = []
    app = Kupala()
    app.mail.add('default', Mailer(InMemoryTransport(storage), from_address='root <root@localhost>'))
    await app.mail.send(Email(subject='test', text='body'))
    assert len(storage) == 1
    assert storage[0]['From'] == 'root <root@localhost>'
