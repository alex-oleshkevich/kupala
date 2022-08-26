from kupala.application import App, Extension
from kupala.authentication import AuthenticationMiddleware, Authenticator


def use_auth(
    authenticators: list[Authenticator],
) -> Extension:
    """Enable session support."""

    def extension(app: App) -> None:
        app.middleware.use(AuthenticationMiddleware, authenticators=authenticators)

    return extension
