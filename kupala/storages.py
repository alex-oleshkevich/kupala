from deesk.storage import Storage


class Storages:
    def __init__(self, disks: dict[str, Storage], default: str) -> None:
        self._disks = disks
        self._default = default

    def get(self, name: str) -> Storage:
        return self._disks[name]

    def get_default_disk(self) -> Storage:
        return self._disks[self._default]
