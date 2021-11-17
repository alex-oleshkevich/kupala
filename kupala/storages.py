from deesk.storage import Storage


class Storages:
    def __init__(self, disks: dict[str, Storage]) -> None:
        self._disks = disks

    def get(self, name: str) -> Storage:
        return self._disks[name]
