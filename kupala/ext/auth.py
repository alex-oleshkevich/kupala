from kupala.application import App
from kupala.authentication import AuthenticationMiddleware, Authenticator


def use_auth(
    app: App,
    authenticators: list[Authenticator],
) -> None:
    """Enable session support."""

    app.middleware.use(AuthenticationMiddleware, authenticators=authenticators)
