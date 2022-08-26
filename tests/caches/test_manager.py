from kupala.cache import Cache, CacheManager, InMemoryCache


def test_instantiates_with_caches() -> None:
    cache = Cache(InMemoryCache())
    manager = CacheManager(caches={"memory": cache}, default="memory")
    assert manager.get("memory") == cache


def test_default_cache() -> None:
    cache = Cache(InMemoryCache())
    manager = CacheManager(caches={"memory": cache}, default="memory")
    assert manager.default == cache


def test_add_get() -> None:
    cache = Cache(InMemoryCache())
    manager = CacheManager()
    manager.add("memory", cache)
    assert manager.get("memory") == cache
