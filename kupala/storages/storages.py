from __future__ import annotations

import os
import pathlib
from deesk.drivers.fs import LocalFsDriver
from deesk.storage import Storage as BaseStorage


class Storage(BaseStorage):  # pragma: nocover
    def url(self, path: str | os.PathLike) -> str:
        raise NotImplementedError()

    def abspath(self, path: str | os.PathLike) -> str:
        raise NotImplementedError()


class LocalStorage(Storage):
    def __init__(self, base_dir: str | os.PathLike, url_prefix: str = "") -> None:
        self.base_dir = base_dir
        self.url_prefix = url_prefix
        super().__init__(driver=LocalFsDriver(base_dir=base_dir))

    def url(self, path: str | os.PathLike) -> str:
        return f"{self.url_prefix}{path}"

    def abspath(self, path: str | os.PathLike) -> str:
        return str(pathlib.Path(self.base_dir) / path)


class S3Storage(Storage):
    def __init__(
        self,
        bucket: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        url_prefix: str = "",
        link_ttl: int = 300,
        region_name: str | None = None,
        profile_name: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        from deesk.drivers.s3 import S3Driver

        self.url_prefix = url_prefix
        self.link_ttl = link_ttl
        self.driver = S3Driver(
            bucket=bucket,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            profile_name=profile_name,
            endpoint_url=endpoint_url,
        )
        super().__init__(self.driver)

    def url(self, path: str | os.PathLike) -> str:
        return f"{self.url_prefix}{path}"

    def abspath(self, path: str | os.PathLike) -> str:
        return ""


class StorageManager:
    def __init__(self, storages: dict[str, Storage] | None = None, default_storage: str | None = None) -> None:
        self._default_storage_name = default_storage or ""
        self._storages: dict[str, Storage] = storages or {}

    @property
    def default(self) -> Storage:
        if len(self._storages) == 1:
            return list(self._storages.values())[0]
        try:
            return self._storages[self._default_storage_name]
        except KeyError:
            raise KeyError("No default storage configured.")

    def add(self, name: str, storage: Storage) -> StorageManager:
        assert name not in self._storages, f'Storage "{name}" already exists.'
        self._storages[name] = storage
        return self

    def get(self, name: str) -> Storage:
        assert name in self._storages
        return self._storages[name]
