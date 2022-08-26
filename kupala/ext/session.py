import typing
from starsessions import (
    CookieStore,
    InMemoryStore,
    Serializer,
    SessionAutoloadMiddleware,
    SessionMiddleware,
    SessionStore,
)
from starsessions.stores.redis import RedisStore
from urllib.parse import parse_qs, urlparse

from kupala.application import App, Extension


def create_store(app: App, config: str) -> SessionStore:
    if config == "cookie://":
        return CookieStore(app.secret_key)
    elif config.startswith("redis://"):
        url = urlparse(config)
        query = parse_qs(url.query)
        prefix = query.get("prefix", ["kupala."])[0]
        gc_ttl = int(query.get("gc_ttl", ["2592000"])[0])  # default 30 days
        return RedisStore(config, prefix=prefix, gc_ttl=gc_ttl)
    elif config.startswith("memory://"):
        return InMemoryStore()
    raise ValueError(f"Unsupported session store: {config}")


def use_session(
    lifetime: int = 0,
    rolling: bool = True,
    autoload: typing.Iterable[str] | bool | None = True,
    store: str | SessionStore = "cookie://",
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
        if isinstance(store, str):
            store = create_store(app, store)

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
