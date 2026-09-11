import typing
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    demo_api_key: typing.Annotated[SecretStr, Field(min_length=1)] = SecretStr("")
