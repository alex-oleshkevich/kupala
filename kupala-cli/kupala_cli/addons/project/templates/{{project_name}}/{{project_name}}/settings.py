import dataclasses
import enum

from kupala.config import Config, is_unittest_environment

is_testing = is_unittest_environment()
env_prefix = "TEST_" if is_testing else ""
env = Config(env_prefix=env_prefix)


class AppEnv(enum.Enum):
    LOCAL = "locale"
    UNITTEST = "unittest"
    PRODUCTION = "production"


@dataclasses.dataclass(frozen=True)
class Settings:
    debug: bool = env("DEBUG", cast=bool, default=False)
    env: AppEnv = env("APP_ENV", cast=AppEnv, default=AppEnv.LOCAL)


@dataclasses.dataclass(frozen=True)
class UnitTestSettings(Settings):
    """Settings for unit tests.
    Prefer to use hardcoded values for unit tests and not rely on environment variables."""

    debug: bool = True


settings = UnitTestSettings() if is_testing else Settings()
