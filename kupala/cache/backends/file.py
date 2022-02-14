from __future__ import annotations

import anyio
import hashlib
import os
import pickle
import tempfile
import time
import typing
import urllib.parse
from starlette.concurrency import run_in_threadpool

from kupala.cache.backends import CacheBackend


class FileCache(CacheBackend):
    file_extension: str = '.cache'

    def __init__(self, directory: str | os.PathLike) -> None:
        self.directory = str(directory)

    async def get(self, key: str) -> bytes | None:
        path = self._make_path(key)
        if await run_in_threadpool(os.path.exists, path):
            try:
                async with await anyio.open_file(path, 'rb') as f:
                    contents = pickle.loads(await f.read())
                    if time.time() < contents.get('expires', 0):
                        return contents['data']
                    else:
                        await self.delete(key)
            except FileNotFoundError:  # pragma: no cover
                return None
        return None

    async def get_many(self, keys: typing.Iterable[str]) -> dict[str, bytes | None]:
        values: dict[str, typing.Optional[bytes]] = {}

        async def getter(key: str) -> None:
            values[key] = await self.get(key)

        async with anyio.create_task_group() as tg:
            for key in keys:
                tg.start_soon(getter, key)
        return values

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        await self._mkdir()
        dest_file = self._make_path(key)
        _, tmp_file = await run_in_threadpool(tempfile.mkstemp, dir=self.directory)  # type: ignore[call-arg]
        async with await anyio.open_file(tmp_file, 'wb') as f:
            moved = False
            try:
                await f.write(pickle.dumps({'data': value, 'expires': time.time() + ttl}))
                await run_in_threadpool(os.rename, tmp_file, dest_file)
                moved = True
            finally:
                if not moved:
                    await run_in_threadpool(os.remove, tmp_file)

    async def set_many(self, value: dict[str, bytes], ttl: int) -> None:
        async def setter(key_: str, value_: bytes, ttl_: int) -> None:
            await self.set(key_, value_, ttl_)

        async with anyio.create_task_group() as tg:
            for key, data in value.items():
                tg.start_soon(setter, key, data, ttl)

    async def delete(self, key: str) -> None:
        if await self.exists(key):
            path = self._make_path(key)
            await run_in_threadpool(os.remove, path)

    async def delete_many(self, keys: typing.Iterable[str]) -> None:
        async with anyio.create_task_group() as tg:
            for key in keys:
                tg.start_soon(self.delete, key)

    async def clear(self) -> None:
        for file in await run_in_threadpool(os.listdir, self.directory):
            file_path = os.path.join(self.directory, file)
            await run_in_threadpool(os.remove, file_path)

    async def increment(self, key: str, step: int) -> None:
        counter = int(await self.get(key) or b'0') + 1
        await self.set(key, str(counter).encode(), 999_999_999)

    async def decrement(self, key: str, step: int) -> None:
        counter = int(await self.get(key) or b'0') - 1
        await self.set(key, str(counter).encode(), 999_999_999)

    async def touch(self, key: str, delta: int) -> None:
        data = await self.get(key)
        if data:
            await self.set(key, data, delta)

    async def exists(self, key: str) -> bool:
        return await run_in_threadpool(os.path.exists, self._make_path(key))

    def _make_path(self, key: str) -> str:
        return os.path.join(self.directory, self._key_to_file(key))

    def _key_to_file(self, key: str) -> str:
        return os.path.join(self.directory, ''.join([hashlib.md5(key.encode()).hexdigest(), self.file_extension]))

    async def _mkdir(self) -> None:
        old_umask = os.umask(0o077)
        try:
            await run_in_threadpool(os.makedirs, self.directory, 0o700, exist_ok=True)
        finally:
            os.umask(old_umask)

    @classmethod
    def from_url(cls: typing.Type[FileCache], url: str) -> FileCache:
        """
        Create backend from URLs like:

        file:///tmp
        """
        components = urllib.parse.urlparse(url)
        return cls(directory=components.path)
