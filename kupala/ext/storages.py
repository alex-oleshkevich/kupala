import typing

from kupala.application import App, Extension
from kupala.storages.storages import Storage, StorageManager


def use_storages(
    storage: Storage,
    extra: typing.Mapping[str, Storage] | None = None,
) -> Extension:
    """Enable storages support."""

    def extension(app: App) -> None:
        manager = StorageManager({"default": storage, **(extra or {})})
        app.state.storages = manager
        app.state.storage = manager.default

    return extension
