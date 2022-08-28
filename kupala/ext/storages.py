import typing

from kupala.application import App
from kupala.storages.storages import Storage, StorageManager


def use_storages(
    app: App,
    storage: Storage,
    extra: typing.Mapping[str, Storage] | None = None,
) -> None:
    """Enable storages support."""

    manager = StorageManager({"default": storage, **(extra or {})})
    app.state.storages = manager
    app.state.storage = manager.default

    app.add_dependency(StorageManager, lambda _: manager)
    app.add_dependency(Storage, lambda _: manager.default)
