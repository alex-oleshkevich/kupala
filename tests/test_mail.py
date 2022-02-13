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
    app.mailers.add('default', mailer)
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
        plugins=[JinjaRendererPlugin(app.jinja_env)],
    )
    app.mailers.add('default', mailer)
    await send_templated_mail(mailer, to='root@localhost', subject='test', html_template='index.html')
    assert len(storage) == 1
    assert storage[0]['From'] == 'root <root@localhost>'
    assert storage[0].get_payload() == 'base mail\n'


def test_mail_use() -> None:
    app = Kupala()
    app.mailers.use('memory://')
    assert isinstance(app.mailers.get_default(), Mailer)

    with pytest.raises(KeyError, match='No mailer named'):
        app.mailers.get('missing')


def test_mail_add() -> None:
    storage: list[Message] = []
    app = Kupala()
    app.mailers.add('default', Mailer(InMemoryTransport(storage)))
    assert isinstance(app.mailers.get_default(), Mailer)


@pytest.mark.asyncio
async def test_mail_send() -> None:
    storage: list[Message] = []
    app = Kupala()
    app.mailers.add('default', Mailer(InMemoryTransport(storage), from_address='root <root@localhost>'))
    await app.mailers.send(Email(subject='test', text='body'))
    assert len(storage) == 1
    assert storage[0]['From'] == 'root <root@localhost>'
