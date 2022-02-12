import itsdangerous
import pytest

from kupala.application import Kupala
from kupala.responses import PlainTextResponse
from kupala.security.signing import Signer
from kupala.testclient import TestClient


@pytest.fixture()
def secret_key() -> str:
    return 'key!'


@pytest.fixture()
def signer(secret_key: str) -> Signer:
    return Signer(secret_key)


def test_signer(signer: Signer) -> None:
    value = 'value'
    signed_value = signer.sign(value)
    assert signer.unsign(signed_value) == value.encode()


def test_signer_raises(signer: Signer) -> None:
    value = 'value'
    with pytest.raises(itsdangerous.BadSignature):
        signer.unsign(value)


def test_signer_safe_unsign_ok(signer: Signer) -> None:
    signed_value = signer.sign('value')
    ok, value = signer.safe_unsign(signed_value)
    assert ok is True
    assert value == b'value'


def test_signer_safe_unsign_fail(signer: Signer) -> None:
    ok, value = signer.safe_unsign('value')
    assert ok is False
    assert value is None


def test_timed_signer(signer: Signer) -> None:
    app = Kupala()
    value = 'value'
    signed_value = app.state.signer.timed_sign(value)
    assert app.state.signer.timed_unsign(signed_value, 10) == value.encode()


def test_timed_signer_raises_for_invalid_value(signer: Signer) -> None:
    value = 'value'
    with pytest.raises(itsdangerous.BadSignature):
        signer.timed_unsign(value, 10)


def test_signer_safe_timed_unsign_ok(signer: Signer) -> None:
    signed_value = signer.timed_sign('value')
    ok, value = signer.safe_timed_unsign(signed_value, 10)
    assert ok is True
    assert value == b'value'


def test_signer_safe_timed_unsign_fail(signer: Signer) -> None:
    ok, value = signer.safe_timed_unsign('value', 10)
    assert ok is False
    assert value is None


@pytest.mark.asyncio
async def test_is_injectable() -> None:
    async def view(signer: Signer) -> PlainTextResponse:
        return PlainTextResponse(signer.sign('value'))

    app = Kupala()
    app.routes.add('/', view)

    client = TestClient(app)
    assert app.state.signer.unsign(client.get('/').text) == b'value'
