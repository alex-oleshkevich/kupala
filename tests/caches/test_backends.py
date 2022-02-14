import os
import pytest
import typing

from kupala.cache import CacheBackend, InMemoryCache
from kupala.cache.dummy import DummyCache
from kupala.cache.redis import RedisCache


async def in_memory_factory() -> InMemoryCache:
    return InMemoryCache()


async def redis_factory() -> RedisCache:
    redis = RedisCache(os.environ.get('REDIS_URL', 'redis://'))
    await redis.clear()
    return redis


backends = [redis_factory, in_memory_factory]


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_set_get(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    expected = b'value'
    await backend.set('key', expected, ttl=3600)
    assert await backend.get('key') == expected


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_get_returns_none_for_missing(
    backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]
) -> None:
    backend = await backend_factory()
    assert await backend.get('key') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_get_returns_none_for_expired(
    backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]
) -> None:
    backend = await backend_factory()
    await backend.set('key', b'', ttl=-1)
    assert await backend.get('key') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_get_set_many(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    expected = {'key1': b'value1', 'key2': b'value2'}
    await backend.set_many(expected, ttl=3600)
    assert await backend.get_many(['key1', 'key2']) == expected


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_get_set_many_excludes_expired(
    backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]
) -> None:
    backend = await backend_factory()
    expected = {'key1': b'value1', 'key2': b'value2'}
    await backend.set('key3', b'value3', ttl=3600)
    await backend.set('key4', b'value4', ttl=-1)  # set key and immediately expire it
    await backend.set_many(expected, ttl=3600)
    assert await backend.get_many(['key1', 'key2', 'key3', 'key4']) == {
        'key1': b'value1',
        'key2': b'value2',
        'key3': b'value3',
    }


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_delete(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.set('key', b'value', 3600)
    await backend.delete('key')
    assert await backend.get('key') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_delete_not_fails_for_missing_keys(
    backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]
) -> None:
    backend = await backend_factory()
    await backend.delete('key')
    assert await backend.get('key') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_delete_many(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.set('key', b'value', 3600)
    await backend.delete_many(['key', 'key2'])  # missing key2 must not cause error
    assert await backend.get('key') is None
    assert await backend.get('key2') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_clear(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.set('key', b'value', 3600)
    await backend.set('key2', b'value', 3600)
    await backend.clear()
    assert await backend.get('key') is None
    assert await backend.get('key2') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_increments_creates_key(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.increment('counter', 1)
    assert await backend.get('counter') == b'1'


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_increments_existing(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.set('counter', b'1', 3600)
    await backend.increment('counter', 1)
    assert await backend.get('counter') == b'2'


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_decrements_creates_key(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.decrement('counter', 1)
    assert await backend.get('counter') == b'-1'


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_decrements_existing(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.set('counter', b'1', 3600)
    await backend.decrement('counter', 1)
    assert await backend.get('counter') == b'0'


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_touch(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.set('key', b'value', 3600)
    await backend.touch('key', 0)
    assert await backend.get('key') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_touch_missed_key(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.touch('key2', 0)
    assert await backend.get('key2') is None


@pytest.mark.parametrize('backend_factory', backends)
@pytest.mark.asyncio
async def test_exists(backend_factory: typing.Callable[[], typing.Awaitable[CacheBackend]]) -> None:
    backend = await backend_factory()
    await backend.set('key1', b'value', 3600)
    assert await backend.exists('key1') is True
    assert await backend.exists('key2') is False


@pytest.mark.asyncio
async def test_dummy_cache() -> None:
    backend = DummyCache()
    assert await backend.get('key') is None
    assert await backend.get_many(['key']) == {}
    assert await backend.set('key', b'value', 10) is None
    assert await backend.set_many({}, 10) is None
    assert await backend.delete('key') is None
    assert await backend.delete_many(['key']) is None
    assert await backend.clear() is None
    assert await backend.increment('counter', 1) is None
    assert await backend.decrement('counter', 1) is None
    assert await backend.touch('key', 10) is None
    assert await backend.exists('key') is False
