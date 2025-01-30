from __future__ import annotations
import dataclasses
import datetime
import enum
import os
import typing

import anyio
from async_storages import (
    BaseBackend,
    FileStorage,
    FileSystemBackend,
    MemoryBackend,
    S3Backend,
    generate_file_path,
    sanitize_filename,
)
from async_storages.backends.base import AdaptedBytesIO, AsyncFileLike, AsyncReader
from async_storages.contrib.starlette import FileServer
from starlette.datastructures import UploadFile

__all__ = [
    "FileStorage",
    "S3Backend",
    "MemoryBackend",
    "FileSystemBackend",
    "BaseBackend",
    "sanitize_filename",
    "generate_file_path",
    "StorageType",
    "StorageConfig",
    "Files",
    "FileServer",
    "AsyncFileLike",
    "AdaptedBytesIO",
    "AsyncReader",
    "LocalConfig",
    "S3Config",
    "MemoryConfig",
]


class StorageType(enum.StrEnum):
    S3 = "s3"
    LOCAL = "local"
    MEMORY = "memory"


@dataclasses.dataclass(frozen=True)
class LocalConfig:
    directory: str
    url_prefix: str
    make_dirs: bool = True
    make_dirs_exists_ok: bool = True
    make_dirs_permissions: int = 0o777


@dataclasses.dataclass(frozen=True)
class S3Config:
    bucket: str
    access_key: str
    secret_key: str
    region: str
    endpoint: str
    signed_link_ttl: datetime.timedelta = datetime.timedelta(hours=1)


@dataclasses.dataclass(frozen=True)
class MemoryConfig:
    pass


type StorageConfig = LocalConfig | S3Config | MemoryConfig


class Files:
    def __init__(self, backend: BaseBackend) -> None:
        self._storage = FileStorage(backend)

    async def write(
        self,
        path: str | os.PathLike[typing.AnyStr],
        data: bytes | AsyncReader | typing.BinaryIO,
    ) -> None:
        return await self._storage.write(path, data)

    async def open(self, path: str | os.PathLike[typing.AnyStr]) -> AsyncFileLike:
        return await self._storage.open(path)

    async def exists(self, path: str | os.PathLike[typing.AnyStr]) -> bool:
        return await self._storage.exists(path)

    async def delete(self, path: str | os.PathLike[typing.AnyStr]) -> None:
        return await self._storage.delete(path)

    async def url(self, path: str | os.PathLike[typing.AnyStr]) -> str:
        return await self._storage.url(path)

    def abspath(self, path: str) -> str:
        return self._storage.abspath(path)

    async def iterator(self, path: str, chunk_size: int = 1024 * 64) -> typing.AsyncIterable[bytes]:
        return await self._storage.iterator(path, chunk_size)

    async def upload(
        self,
        upload_file: UploadFile,
        destination: str,
        *,
        extra_tokens: typing.Mapping[str, typing.Any] | None = None,
    ) -> str:
        assert upload_file.filename, "Filename is required"
        file_name = generate_file_path(upload_file.filename, destination, extra_tokens=extra_tokens or {})
        await self._storage.write(file_name, upload_file)
        return file_name

    async def upload_many(
        self,
        destination: str,
        upload_files: typing.Sequence[UploadFile],
        extra_tokens: typing.Mapping[str, typing.Any] | None = None,
    ) -> str:
        file_names: list[str] = []
        extra_tokens = extra_tokens or {}

        async def worker(file: UploadFile) -> None:
            assert file.filename, "Filename is required"
            file_path = await self.upload(file, destination, extra_tokens=extra_tokens)
            file_names.append(file_path)

        async with anyio.create_task_group() as tg:
            for file in upload_files:
                tg.start_soon(worker, file)
        return file_names

    async def delete_many(self, file_names: typing.Sequence[str]) -> None:
        async with anyio.create_task_group() as tg:
            for file_name in file_names:
                tg.start_soon(self.delete, file_name)

    @classmethod
    def from_choices(cls, storage_name: str, **storages: StorageConfig) -> FileStorage:
        config = storages[storage_name]
        if isinstance(config, LocalConfig):
            return FileStorage(
                FileSystemBackend(
                    base_dir=config.dir,
                    base_url=config.url_prefix,
                    mkdirs=config.make_dirs,
                    mkdir_exists_ok=config.make_dirs_exists_ok,
                    mkdir_permissions=config.make_dirs_permissions,
                )
            )

        if isinstance(config, S3Config):
            return FileStorage(
                S3Backend(
                    bucket=config.bucket,
                    aws_access_key_id=config.access_key,
                    aws_secret_access_key=config.secret_key,
                    region_name=config.region,
                    endpoint_url=config.endpoint,
                    signed_link_ttl=config.signed_link_ttl.total_seconds(),
                )
            )

        if isinstance(config, MemoryConfig):
            return FileStorage(MemoryBackend())

        raise ValueError(f"Unknown storage type: {config}")
