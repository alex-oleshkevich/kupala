from kupala.cache import Cache, CacheManager, DummyCache, FileCache, InMemoryCache
from kupala.cache.backends.redis import RedisCache


def test_instantiates_with_caches() -> None:
    cache = Cache("memory://")
    manager = CacheManager(caches={"memory": cache}, default="memory")
    assert manager.get("memory") == cache


def test_default_cache() -> None:
    cache = Cache("memory://")
    manager = CacheManager(caches={"memory": cache}, default="memory")
    assert manager.default == cache


def test_add_get() -> None:
    cache = Cache("memory://")
    manager = CacheManager()
    manager.add("memory", cache)
    assert manager.get("memory") == cache


def test_add_in_memory() -> None:
    manager = CacheManager()
    manager.add_in_memory("memory")
    assert isinstance(manager.get("memory").backend, InMemoryCache)


def test_add_dummy() -> None:
    manager = CacheManager()
    manager.add_dummy("cache")
    assert isinstance(manager.get("cache").backend, DummyCache)


def test_file() -> None:
    manager = CacheManager()
    manager.add_file("cache", "/tmp")
    assert isinstance(manager.get("cache").backend, FileCache)


def test_redis() -> None:
    manager = CacheManager()
    manager.add_redis("cache", "redis://")
    assert isinstance(manager.get("cache").backend, RedisCache)
