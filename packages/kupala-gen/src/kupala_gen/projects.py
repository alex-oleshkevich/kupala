import dataclasses
import pathlib
import tomllib
import typing

import click


@dataclasses.dataclass(frozen=True, slots=True)
class Project:
    root: pathlib.Path
    package: pathlib.Path
    package_name: str
    routes_file: pathlib.Path


def load_pyproject(root: pathlib.Path) -> dict[str, typing.Any]:
    path = root / "pyproject.toml"
    try:
        with path.open("rb") as configuration:
            return tomllib.load(configuration)
    except FileNotFoundError:
        raise click.UsageError(f"No pyproject.toml found in {root}.") from None
    except tomllib.TOMLDecodeError as error:
        raise click.UsageError(f"Invalid TOML in {path}: {error}") from None


def discover_project(root: pathlib.Path) -> Project:
    values = load_pyproject(root)
    try:
        (target,) = values["project"]["entry-points"]["kupala.app"].values()
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        raise click.UsageError("The project must declare one kupala.app entry point.")

    if not isinstance(target, str):
        raise click.UsageError("The kupala.app entry point must use module:attribute syntax.")

    module, separator, attribute = target.partition(":")
    if not all((module, separator, attribute)):
        raise click.UsageError("The kupala.app entry point must use module:attribute syntax.")

    package_name, separator, _ = module.rpartition(".")
    if not separator:
        raise click.UsageError("The kupala.app entry point must point inside a package.")

    relative_app = pathlib.Path(*module.split(".")).with_suffix(".py")
    candidates = tuple(path for path in (root / relative_app, root / "src" / relative_app) if path.is_file())
    if len(candidates) != 1:
        raise click.UsageError(f"Could not resolve the application file for {target!r}.")

    application_file = candidates[0]
    package = application_file.parent
    if not (package / "__init__.py").is_file():
        raise click.UsageError(f"Application package has no __init__.py: {package}")

    routes_file = package / "routes.py"
    if not routes_file.is_file():
        routes_file = application_file

    return Project(root, package, package_name, routes_file)
