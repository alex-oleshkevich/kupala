import aioredis
import os
import pytest
import secrets
import tempfile
import typing
from unittest import mock

from kupala.cache import CacheBackend, DummyCache, FileCache, InMemoryCache
from kupala.cache.backends.redis import RedisCache

REDIS_URL = os.environ.get('REDIS_URL', 'redis://')


async def in_memory_factory() -> InMemoryCache:
    return InMemoryCache()


async def redis_factory() -> RedisCache:
    return RedisCache(REDIS_URL, key_prefix='kupala_test_cache_' + secrets.token_hex(4))


async def file_factory() -> FileCache:
    base_directory = tempfile.mkdtemp(prefix='kupala_cache_')
    directory = tempfile.mkdtemp()
    return FileCache(os.path.join(base_directory, directory))


@pytest.mark.asyncio
@pytest.fixture(autouse=True)
async def reset_redis() -> typing.AsyncGenerator[None, None]:
    redis = aioredis.from_url(REDIS_URL)
    await redis.flushdb()
    yield


backends = [redis_factory, in_memory_factory, file_factory]


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
    assert await backend.get_many(['key1', 'key2', 'key3', 'key4', 'key4', 'key5']) == {
        'key1': b'value1',
        'key2': b'value2',
        'key3': b'value3',
        'key4': None,
        'key5': None,
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
    assert await backend.get('key') is None  # type: ignore[func-returns-value]
    assert await backend.get_many(['key']) == {}
    assert await backend.set('key', b'value', 10) is None  # type: ignore[func-returns-value]
    assert await backend.set_many({}, 10) is None  # type: ignore[func-returns-value]
    assert await backend.delete('key') is None  # type: ignore[func-returns-value]
    assert await backend.delete_many(['key']) is None  # type: ignore[func-returns-value]
    assert await backend.clear() is None  # type: ignore[func-returns-value]
    assert await backend.increment('counter', 1) is None  # type: ignore[func-returns-value]
    assert await backend.decrement('counter', 1) is None  # type: ignore[func-returns-value]
    assert await backend.touch('key', 10) is None  # type: ignore[func-returns-value]
    assert await backend.exists('key') is False


def test_inmemory_creates_from_url() -> None:
    backend = InMemoryCache.from_url('memory://')
    assert backend


def test_dummy_creates_from_url() -> None:
    backend = DummyCache.from_url('dummy://')
    assert backend


def test_file_creates_from_url() -> None:
    backend = FileCache.from_url('file:///tmp')
    assert backend.directory == '/tmp'


def test_redis_creates_from_url() -> None:
    backend = RedisCache.from_url('redis://localhost/?key_prefix=kupala')
    assert backend.key_prefix == 'kupala'


@pytest.mark.asyncio
async def test_file_backend_deletes_source_if_cannot_move_tmp_file() -> None:
    tmp_dir = tempfile.mkdtemp()
    backend = FileCache(tmp_dir)
    with mock.patch('pickle.dumps', side_effect=TypeError), pytest.raises(TypeError):
        await backend.set('test', b'', 1)

    assert len(os.listdir(tmp_dir)) == 0
