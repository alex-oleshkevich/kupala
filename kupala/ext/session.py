import typing
from starsessions import CookieStore, Serializer, SessionAutoloadMiddleware, SessionMiddleware, SessionStore

from kupala.application import App, Extension


def use_session(
    lifetime: int = 0,
    rolling: bool = True,
    autoload: typing.Iterable[str] | bool | None = True,
    store: typing.Literal["cookie"] | SessionStore = "cookie",
    cookie_name: str = "session",
    cookie_same_site: str = "lax",
    cookie_https_only: bool = True,
    cookie_domain: str | None = None,
    cookie_path: str | None = "/",
    serializer: Serializer | None = None,
) -> Extension:
    """Enable session support."""

    def extension(app: App) -> None:
        nonlocal store
        if store == "cookie":
            store = CookieStore(app.secret_key)

        app.add_middleware(
            SessionMiddleware,
            lifetime=lifetime,
            rolling=rolling,
            store=store,
            cookie_name=cookie_name,
            cookie_same_site=cookie_same_site,
            cookie_https_only=cookie_https_only,
            cookie_domain=cookie_domain,
            cookie_path=cookie_path,
            serializer=serializer,
        )

        if autoload:
            app.add_middleware(
                SessionAutoloadMiddleware,
                paths=autoload if isinstance(autoload, typing.Iterable) else None,
            )

    return extension
