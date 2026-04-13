from __future__ import annotations

import limits
from limits import RateLimitItem
from limits.aio.strategies import MovingWindowRateLimiter
from limits.storage import Storage

from kupala.error_codes import ErrorCode
from kupala.exceptions import KupalaError


class RateLimitedError(KupalaError):
    error_code = ErrorCode("rate_limited")

    def __init__(self, stats: limits.WindowStats) -> None:
        super().__init__()
        self.stats = stats


class RateLimiter:
    def __init__(self, storage: Storage, namespace: str) -> None:
        self._namespace = namespace
        self._storage = storage

    def moving_window(self, item: RateLimitItem, namespace: str) -> _MovingWindowRateLimiter:
        full_namespace = f"{self._namespace}:{namespace}"
        return _MovingWindowRateLimiter(item, full_namespace)


class _MovingWindowRateLimiter:
    def __init__(self, item: RateLimitItem, storage: Storage, namespace: str) -> None:
        self.item = item
        self.namespace = namespace
        self.storage = self.storage
        self.limiter = MovingWindowRateLimiter(self.storage)

    async def hit(self, actor_id: str) -> bool:
        return await self.limiter.hit(self.item, self.namespace, actor_id)

    async def hit_or_raise(self, actor_id: str) -> None:
        if not await self.hit(actor_id):
            stats = await self.limiter.get_window_stats(self.item, self.namespace, actor_id)
            raise RateLimitedError(stats=stats)

    async def clear(self, actor_id: str) -> None:
        await self.limiter.clear(self.item, self.namespace, actor_id)

    async def reset(self) -> None:
        await self.storage.reset()
