import pytest
from email.message import Message
from mailers import Email, InMemoryTransport, Mailer

from kupala.application import Kupala


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
