import itsdangerous
import pytest
from itsdangerous import Signer, TimestampSigner

from kupala.application import Kupala
from kupala.responses import PlainTextResponse
from kupala.testclient import TestClient


def test_signer() -> None:
    app = Kupala()
    value = 'value'
    signed_value = app.signer.sign(value)
    assert app.signer.unsign(signed_value) == value.encode()


def test_signer_raises() -> None:
    app = Kupala()
    value = 'value'
    with pytest.raises(itsdangerous.BadSignature):
        app.signer.unsign(value)


def test_signer_safe_unsign_ok() -> None:
    app = Kupala()
    signed_value = app.signer.sign('value')
    ok, value = app.signer.safe_unsign(signed_value)
    assert ok is True
    assert value == b'value'


def test_signer_safe_unsign_fail() -> None:
    app = Kupala()
    ok, value = app.signer.safe_unsign('value')
    assert ok is False
    assert value is None


def test_timed_signer() -> None:
    app = Kupala()
    value = 'value'
    signed_value = app.signer.timed_sign(value)
    assert app.signer.timed_unsign(signed_value, 10) == value.encode()


def test_timed_signer_raises_for_invalid_value() -> None:
    app = Kupala()
    value = 'value'
    with pytest.raises(itsdangerous.BadSignature):
        app.signer.timed_unsign(value, 10)


def test_signer_safe_timed_unsign_ok() -> None:
    app = Kupala()
    signed_value = app.signer.timed_sign('value')
    ok, value = app.signer.safe_timed_unsign(signed_value, 10)
    assert ok is True
    assert value == b'value'


def test_signer_safe_timed_unsign_fail() -> None:
    app = Kupala()
    ok, value = app.signer.safe_timed_unsign('value', 10)
    assert ok is False
    assert value is None


@pytest.mark.asyncio
async def test_signer_injection() -> None:
    async def view(signer: Signer) -> PlainTextResponse:
        return PlainTextResponse(signer.sign('value'))

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    assert app.signer.unsign(client.get('/').text) == b'value'


@pytest.mark.asyncio
async def test_timed_signer_injection() -> None:
    async def view(signer: TimestampSigner) -> PlainTextResponse:
        return PlainTextResponse(signer.sign('value'))

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    assert app.signer.timed_unsign(client.get('/').text, 10) == b'value'
