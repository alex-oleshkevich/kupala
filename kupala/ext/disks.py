from kupala.application import Kupala
from kupala.container import Resolver
from kupala.disks.storages import Storage, Storages
from kupala.providers import Provider


class StoragesProvider(Provider):
    def __init__(self, disks: dict[str, Storage], default: str) -> None:
        assert default in disks, 'Default disk must be present in configured disks.'
        self.disks = disks
        self.default = default

    def register(self, app: Kupala) -> None:
        app.services.bind(Storages, Storages(self.disks, default=self.default))
        app.services.factory(Storage, self.get_default_disk)

    def get_default_disk(self, resolver: Resolver) -> Storage:
        return self.disks[self.default]
