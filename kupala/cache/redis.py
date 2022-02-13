from kupala.cache.backend import CacheBackend


class RedisCache(CacheBackend):
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
