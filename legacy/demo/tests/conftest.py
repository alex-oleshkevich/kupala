import typing
import logging
import pytest
from kupala.applications import Kupala
from kupala.testing import AsyncTestClient
from kupala.translations import switch_locale
from kupala.timezone import switch_timezone
from sqlalchemy.ext.asyncio import AsyncSession

from demo.settings import settings, AppEnv, Settings
from demo.app import app as app_


@pytest.fixture(autouse=True)
def configure_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Silence any logging output. This can be overridden in individual tests."""
    caplog.set_level(logging.WARNING)


@pytest.fixture(scope="session", autouse=True)
def app_config() -> Settings:
    """Application configuration.
    It has specific overrides for unit tests."""

    assert settings.app_env == AppEnv.UNITTEST, f"Not running in test environment, it is {settings.app_env}."
    return settings


@pytest.fixture
def app() -> Kupala:
    return app_


@pytest.fixture(autouse=True, scope="session")
def _switch_language() -> typing.Generator[None, None, None]:
    with switch_locale("en"):
        yield


@pytest.fixture(autouse=True, scope="session")
def _switch_timezone() -> typing.Generator[None, None, None]:
    with switch_timezone("UTC"):
        yield


@pytest.fixture
async def dbsession() -> typing.AsyncGenerator[AsyncSession, None]:
    """Get a new async database session for each test."""
    async with database.session(force_rollback=True) as dbsession:
        yield dbsession


@pytest.fixture
async def client(app: Kupala) -> typing.AsyncGenerator[AsyncTestClient, None]:
    async with AsyncTestClient(app) as client:
        yield client
