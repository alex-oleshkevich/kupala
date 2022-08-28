import typing

from kupala.application import App
from kupala.cache import Cache, CacheManager
from kupala.cache.cache import backend_from_url
from kupala.cache.compressors import CacheCompressor
from kupala.cache.serializers import CacheSerializer


def use_cache(
    app: App,
    default: str | Cache = "memory://",
    prefix: str = "",
    serializer: CacheSerializer | None = None,
    compressor: CacheCompressor | None = None,
    extra: typing.Mapping[str, Cache] | None = None,
) -> None:
    """Enable cache support."""

    if isinstance(default, str):
        default = Cache(backend_from_url(default), prefix=prefix, serializer=serializer, compressor=compressor)

    manager = CacheManager({"default": default, **(extra or {})})
    app.state.caches = manager
    app.state.cache = manager.default
    app.add_dependency(CacheManager, lambda _: manager)
    app.add_dependency(Cache, lambda _: manager.default)
