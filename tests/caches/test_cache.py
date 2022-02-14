import pytest
from datetime import timedelta

from kupala.cache import Cache, InMemoryCache


@pytest.fixture()
def cache() -> Cache:
    return Cache(backend=InMemoryCache(), prefix='cache_')


@pytest.mark.asyncio
async def test_requires_url_or_backend() -> None:
    with pytest.raises(AssertionError, match='Either "url" or "backend" argument is required.'):
        Cache()


@pytest.mark.asyncio
async def test_creates_backend_from_url() -> None:
    cache = Cache('memory://')
    assert isinstance(cache.backend, InMemoryCache)


@pytest.mark.asyncio
async def test_raises_for_unknown_backend() -> None:
    with pytest.raises(KeyError, match='Unknown backend: unknown://'):
        Cache('unknown://')


@pytest.mark.asyncio
async def test_get_set_delete_exists(cache: Cache) -> None:
    value = 'value'
    await cache.set('key', value, 3600)
    assert await cache.exists('key')

    assert await cache.get('key') == value
    await cache.delete('key')
    assert not await cache.exists('key')


@pytest.mark.asyncio
async def test_get_set_delete_many(cache: Cache) -> None:
    value = {'key1': 'value1', 'key2': 'value2'}
    await cache.set_many(value, 3600)
    assert await cache.exists('key1')
    assert await cache.exists('key2')
    assert await cache.get_many(['key1', 'key2']) == value
    await cache.delete_many(['key1', 'key2'])
    assert not await cache.exists('key1')
    assert not await cache.exists('key2')


@pytest.mark.asyncio
async def test_get_or_set(cache: Cache) -> None:
    value = 'value'
    assert not await cache.exists('key')

    await cache.get_or_set('key', value, 3600)
    assert await cache.exists('key')

    assert await cache.get_or_set('key', value, 3600) == value


@pytest.mark.asyncio
async def test_pull(cache: Cache) -> None:
    value = 'value'
    await cache.set('key', value, 3600)
    assert await cache.pull('key')
    assert not await cache.exists('key')


@pytest.mark.asyncio
async def test_clear(cache: Cache) -> None:
    value = 'value'
    await cache.set('key', value, 3600)
    await cache.clear()
    assert not await cache.exists('key')


@pytest.mark.asyncio
async def test_touch(cache: Cache) -> None:
    value = 'value'
    await cache.set('key', value, 3600)
    await cache.touch('key', -1)
    assert not await cache.exists('key')


@pytest.mark.asyncio
async def test_increment_decrement(cache: Cache) -> None:
    await cache.increment('counter')
    assert await cache.get('counter', 1)
    await cache.decrement('counter')
    assert await cache.get('counter') == 0


@pytest.mark.asyncio
async def test_set_timedelta(cache: Cache) -> None:
    await cache.set('key', 'value', timedelta(hours=1))
    assert await cache.exists('key')


@pytest.mark.asyncio
async def test_get_or_set_timedelta(cache: Cache) -> None:
    await cache.get_or_set('key', 'value', timedelta(hours=1))
    assert await cache.exists('key')


@pytest.mark.asyncio
async def test_set_many(cache: Cache) -> None:
    await cache.set_many({'key': 'value'}, timedelta(hours=1))
    assert await cache.exists('key')
