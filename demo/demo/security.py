import hmac
import typing

from demo.settings import Settings
from kupala.errors import InvalidCredentialsError
from kupala.security import APIKey, BasicAuth, BasicCredentials, Identity


def authenticate_api_key(key: str, settings: Settings) -> Identity[str]:
    expected = settings.demo_api_key.get_secret_value()
    if not hmac.compare_digest(key.encode(), expected.encode()):
        raise InvalidCredentialsError("Invalid demo API key.")
    return Identity("demo")


type DemoAPIKey = typing.Annotated[
    Identity[str],
    APIKey[str](
        name="demoKey",
        key_name="X-Demo-Key",
        location="header",
        authenticate=authenticate_api_key,
    ),
]


def authenticate_basic(credentials: BasicCredentials, settings: Settings) -> Identity[str]:
    username_matches = hmac.compare_digest(credentials.username.encode(), b"demo")
    password_matches = hmac.compare_digest(
        credentials.password.encode(),
        settings.demo_api_key.get_secret_value().encode(),
    )
    if not username_matches or not password_matches:
        raise InvalidCredentialsError("Invalid username or password.")
    return Identity(credentials.username)


type DemoBasicIdentity = typing.Annotated[
    Identity[str],
    BasicAuth[str](realm="Kupala demo", name="demoBasic", authenticate=authenticate_basic),
]
