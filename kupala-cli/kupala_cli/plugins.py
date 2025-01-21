import importlib
import typing
from importlib.metadata import entry_points

import click

type AppPlugin = typing.Callable[[click.Group], None]


def discover_plugins(group: str) -> typing.Generator[AppPlugin, None, None]:
    plugin_specs = entry_points(group=group)
    for plugin_spec in plugin_specs:
        module_path, attr = plugin_spec.value.split(":")
        module = importlib.import_module(module_path)
        plugin: AppPlugin = getattr(module, attr)
        yield plugin
