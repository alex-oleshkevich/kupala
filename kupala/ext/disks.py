from dataclasses import dataclass, field

import functools
import typing

from kupala.application import Kupala
from kupala.providers import Provider
from kupala.storages.storages import LocalStorage, S3Storage, Storage, Storages

DRIVER_MAP = {
    'local': LocalStorage,
    's3': S3Storage,
}


@dataclass
class FileStorage:
    driver: typing.Union[str, Storage]
    options: dict[str, typing.Any] = field(default_factory=dict)


@dataclass
class StorageConfig:
    default: str = 'local'
    drivers: dict[str, FileStorage] = field(default_factory=dict)

    @typing.overload
    def add_disk(self, name: str, driver: typing.Literal["local"], *, base_dir: str, **options: typing.Any) -> None:
        ...

    @typing.overload
    def add_disk(
        self,
        name: str,
        driver: typing.Literal["s3"],
        *,
        bucket: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str,
        **options: typing.Any,
    ) -> None:
        ...

    def add_disk(self, name: str, driver: typing.Literal["local", "s3"], **options: typing.Any) -> None:
        self.drivers[name] = FileStorage(driver=driver, options=options)


class StoragesProvider(Provider):
    def __init__(self, storages: dict[str, typing.Union[FileStorage, Storage]], default: str) -> None:
        assert default in storages, 'Default disk must be present in configured disks.'
        self.storages = storages
        self.default = default

    def register(self, app: Kupala) -> None:
        for name, storage_config in self.storages.items():
            app.services.factory(f'storage.{name}', functools.partial(self.make_storage, storage_config))

        app.services.alias(f'storage.{self.default}', Storage)
        app.services.bind(
            Storages,
            Storages(
                storages={name: functools.partial(app.resolve, f'storage.{name}') for name in self.storages},
                default=self.default,
            ),
        )

    def make_storage(self, storage_config: FileStorage) -> Storage:
        if isinstance(storage_config.driver, Storage):
            return storage_config.driver

        driver_class = DRIVER_MAP[storage_config.driver]
        return driver_class(**storage_config.options)
