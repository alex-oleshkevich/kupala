from __future__ import annotations

import os
import pathlib
import typing
from deesk.drivers.fs import LocalFsDriver
from deesk.storage import Storage as BaseStorage

from kupala.di import injectable


@injectable(from_app_factory=lambda app: app.state.storages.default)
class Storage(BaseStorage):  # pragma: nocover
    async def url(self, path: str | os.PathLike) -> str:
        raise NotImplementedError()

    def abspath(self, path: str | os.PathLike) -> str:
        raise NotImplementedError()


class LocalStorage(Storage):
    def __init__(self, base_dir: str | os.PathLike) -> None:
        self.base_dir = base_dir
        super().__init__(driver=LocalFsDriver(base_dir=base_dir))

    async def url(self, path: str | os.PathLike) -> str:
        return str(path)

    def abspath(self, path: str | os.PathLike) -> str:
        return str(pathlib.Path(self.base_dir) / path)


class S3Storage(Storage):
    def __init__(self, link_ttl: int = 300, **kwargs: typing.Any) -> None:
        from deesk.drivers.s3 import S3Driver

        self.link_ttl = link_ttl
        self.driver = S3Driver(**kwargs)
        super().__init__(self.driver)

    async def url(self, path: str | os.PathLike) -> str:
        async with self.driver.session.client('s3', endpoint_url=self.driver.endpoint_url) as client:
            return await client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.driver.bucket, 'Key': path},
                ExpiresIn=self.link_ttl,
            )

    def abspath(self, path: str | os.PathLike) -> str:
        return ''


@injectable(from_app_factory=lambda app: app.state.storages)
class StorageManager:
    def __init__(self, storages: dict[str, Storage] | None = None, default_storage: str | None = None) -> None:
        self._default_storage_name = default_storage or ''
        self._storages: dict[str, Storage] = storages or {}

    @property
    def default(self) -> Storage:
        if len(self._storages) == 1:
            return list(self._storages.values())[0]
        try:
            return self._storages[self._default_storage_name]
        except KeyError:
            raise KeyError('No default storage configured.')

    def add(self, name: str, storage: Storage) -> StorageManager:
        assert name not in self._storages, f'Storage "{name}" already exists.'
        self._storages[name] = storage
        return self

    def add_local(self, name: str, base_dir: str | os.PathLike) -> StorageManager:
        self.add(name, LocalStorage(base_dir))
        return self

    def add_s3(
        self,
        name: str,
        bucket: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str = None,
        profile_name: str = None,
        endpoint_url: str = None,
        link_ttl: int = 300,
    ) -> StorageManager:
        self.add(
            name,
            S3Storage(
                bucket=bucket,
                aws_secret_access_key=aws_secret_access_key,
                aws_access_key_id=aws_access_key_id,
                region_name=region_name,
                profile_name=profile_name,
                endpoint_url=endpoint_url,
                link_ttl=link_ttl,
            ),
        )
        return self

    def get(self, name: str) -> Storage:
        assert name in self._storages
        return self._storages[name]

    def set_default(self, name: str) -> StorageManager:
        self._default_storage_name = name
        return self
