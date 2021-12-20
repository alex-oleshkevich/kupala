import os
import pathlib
import typing as t
from deesk.drivers.fs import LocalFsDriver
from deesk.storage import Storage as BaseStorage


class Storage(BaseStorage):
    async def url(self, path: t.Union[str, os.PathLike]) -> str:
        raise NotImplementedError()

    def abspath(self, path: t.Union[str, os.PathLike]) -> str:
        raise NotImplementedError()


class LocalStorage(Storage):
    def __init__(self, base_dir: t.Union[str, os.PathLike]) -> None:
        self.base_dir = base_dir
        super().__init__(driver=LocalFsDriver(base_dir=base_dir))

    async def url(self, path: t.Union[str, os.PathLike]) -> str:
        return str(path)

    def abspath(self, path: t.Union[str, os.PathLike]) -> str:
        return str(pathlib.Path(self.base_dir) / path)


class S3Storage(Storage):
    def __init__(self, link_ttl: int = 300, **kwargs: t.Any) -> None:
        from deesk.drivers.s3 import S3Driver

        self.link_ttl = link_ttl
        self.driver = S3Driver(**kwargs)
        super().__init__(self.driver)

    async def url(self, path: t.Union[str, os.PathLike]) -> str:
        async with self.driver.session.client('s3', endpoint_url=self.driver.endpoint_url) as client:
            return await client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.driver.bucket, 'Key': path},
                ExpiresIn=self.link_ttl,
            )

    def abspath(self, path: t.Union[str, os.PathLike]) -> str:
        return ''


class Storages:
    def __init__(self, disks: dict[str, Storage], default: str) -> None:
        self._disks = disks
        self._default = default

    def get(self, name: str) -> Storage:
        """Get disk by name."""
        return self._disks[name]

    def get_default_disk(self) -> Storage:
        """Get default configured disk."""
        return self._disks[self._default]

    def get_or_default(self, name: t.Optional[str]) -> Storage:
        """Retrieve disk by name or return default if missing."""
        return self._disks[name] if name is not None and name in self._disks else self.get_default_disk()
