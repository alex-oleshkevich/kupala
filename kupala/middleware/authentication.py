import imia
import typing
from imia import BaseAuthenticator

from kupala.middleware import Middleware


class AuthenticationMiddleware(imia.AuthenticationMiddleware):  # pragma: nocover
    @classmethod
    def configure(
        cls,
        authenticators: list[BaseAuthenticator],
        on_failure: str = 'do_nothing',
        redirect_to: str = '/',
        exclude_patterns: list[str | typing.Pattern] = None,
        include_patterns: list[str | typing.Pattern] = None,
    ) -> Middleware:
        return Middleware(
            cls,
            authenticators=authenticators,
            on_failure=on_failure,
            redirect_to=redirect_to,
            exclude_patterns=exclude_patterns,
            include_patterns=include_patterns,
        )
