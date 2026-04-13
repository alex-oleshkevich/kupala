import dataclasses
import enum
import pathlib
import datetime

from kupala.config import Config, detect_environment
from starlette.datastructures import CommaSeparatedStrings

package_dir = pathlib.Path(__file__).parent
repo_dir = package_dir.parent


class AppEnv(enum.StrEnum):
    LOCAL = "local"
    UNITTEST = "unittest"
    PRODUCTION = "production"


app_env = detect_environment(AppEnv, fallback=AppEnv.LOCAL, unittests=AppEnv.UNITTEST)
env = Config(
    env_prefix="",
    env_files=[
        repo_dir / ".env",
        repo_dir / f".env.{app_env}",
        repo_dir / f".env.{app_env}.local",
    ],
)


@dataclasses.dataclass(frozen=True)
class Settings:
    debug: bool = env("DEBUG", cast=bool, default=False)
    app_env: AppEnv = app_env
    app_name: str = env("APP_NAME", default="Demo")
    app_url: str = env("APP_URL", default="http://localhost:8000")
    trusted_hosts: list[str] = env(
        "TRUSTED_HOSTS", cast=CommaSeparatedStrings, default=["127.0.0.1", "localhost", "testserver"]
    )

    secret_key: str = env("SECRET_KEY")
    encryption_key: str = env("ENCRYPTION_KEY")

    # session settings
    session_lifetime: datetime.timedelta = datetime.timedelta(days=14)
    session_rolling: bool = True

    # databases
    database_url: str = env("DATABASE_URL")
    redis_url: str = env("REDIS_URL", default="redis://")

    # internationalization
    language: str = env("APP_LANG", default="en")
    supported_languages: list[str] = dataclasses.field(default_factory=lambda: ["en"])

    timezone: str = env("APP_TIMEZONE", default="UTC")

    # email
    email_url: str = env("EMAIL_URL", default="console://?stream=stderr")
    email_from_name: str = env("EMAIL_FROM_NAME", default="Example")
    email_from_address: str = env("EMAIL_FROM_ADDRESS", default="hello@example.com")

    # file storage
    file_storage: str = env("FILE_STORAGE", default="local")
    file_local_upload_dir: str = env("FILE_UPLOAD_DIR", default=repo_dir / "uploads")
    file_s3_bucket: str = env("FILE_S3_BUCKET", default="")
    file_s3_access_key: str = env("FILE_S3_ACCESS_KEY", default="")
    file_s3_secret_key: str = env("FILE_S3_SECRET_KEY", default="")
    file_s3_region: str = env("FILE_S3_REGION", default="")

    # release options
    release_commit: str = ""
    release_branch: str = ""
    release_date: str = ""
    release_version: str = ""

    # cache options
    cache_url: str = env("CACHE_URL", default="memory://")


settings = Settings()
