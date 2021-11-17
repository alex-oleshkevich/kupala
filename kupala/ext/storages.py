from deesk.storage import Storage

from kupala.application import Kupala
from kupala.container import Resolver
from kupala.providers import Provider
from kupala.storages import Storages


class StoragesProvider(Provider):
    def __init__(self, disks: dict[str, Storage], default: str) -> None:
        self.disks = disks
        self.default = default

    def register(self, app: Kupala) -> None:
        app.services.bind(Storages, Storages(self.disks))
        app.services.factory(Storage, self.get_default_disk)

    def get_default_disk(self, resolver: Resolver) -> Storage:
        return self.disks[self.default]
