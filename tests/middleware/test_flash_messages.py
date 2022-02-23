import pytest
import typing as t
from starsessions import SessionMiddleware

from kupala.application import Kupala
from kupala.middleware import Middleware
from kupala.middleware.flash_messages import FlashBag, FlashMessage, FlashMessagesMiddleware, MessageCategory, flash
from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.testclient import TestClient


@pytest.mark.parametrize('storage', ['session'])
def test_flash_messages(storage: t.Literal['session']) -> None:
    def set_view(request: Request) -> JSONResponse:
        flash(request).success('This is a message.')
        return JSONResponse({})

    def get_view(request: Request) -> JSONResponse:
        bag = flash(request)
        return JSONResponse({'messages': list(bag)})

    app = Kupala(
        middleware=[
            Middleware(SessionMiddleware, secret_key='key!', autoload=True),
            Middleware(FlashMessagesMiddleware, storage=storage),
        ]
    )
    app.routes.add('/set', set_view, methods=['post'])
    app.routes.add('/get', get_view)

    client = TestClient(app)
    client.post('/set')

    response = client.get('/get')
    assert response.json()['messages'] == [{'category': 'success', 'message': 'This is a message.'}]

    # must be empty after reading messages
    response = client.get('/get')
    assert response.json()['messages'] == []


def test_flash_messages_session_storages_requires_session() -> None:
    app = Kupala()

    with pytest.raises(KeyError) as ex:
        client = TestClient(FlashMessagesMiddleware(app, storage='session'))
        client.get('/')
    assert ex.value.args[0] == 'Sessions are disabled. Flash messages depend on SessionMiddleware.'


def test_flash_bag() -> None:
    bag = FlashBag()
    bag.add('success', FlashBag.Category.SUCCESS)
    bag.success('success')
    bag.error('error')
    bag.warning('warning')
    bag.info('info')
    bag.debug('debug')
    assert len(bag) == 6
    assert bool(bag) is True

    bag.clear()
    assert len(bag) == 0
    assert bool(bag) is False


def test_flash_messages_by_category() -> None:
    bag = FlashBag()
    bag.success('one')
    bag.error('two')

    assert bag.get_by_category(MessageCategory.SUCCESS) == [FlashMessage('success', 'one')]
    assert len(bag.get_by_category(MessageCategory.SUCCESS)) == 0

    assert bag.get_by_category(MessageCategory.ERROR) == [FlashMessage('error', 'two')]
    assert len(bag.get_by_category(MessageCategory.ERROR)) == 0


def test_flash_message() -> None:
    message = FlashMessage('info', 'hello')
    assert str(message) == 'hello'
