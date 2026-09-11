import dataclasses
import pathlib
import typing


@dataclasses.dataclass
class Question: ...


@dataclasses.dataclass
class Package: ...


class Context:
    project_name: str
    package_name: str
    project_root: pathlib.Path
    pyproject_path: pathlib.Path
    pyproject_data: dict[str, typing.Any]

    def render_template(self, template_name: str, context: dict[str, typing.Any]) -> str: ...
    def install_template(self, template_name: str, target_file: str, context: dict[str, typing.Any]) -> None: ...
    def add_dependency(self, package: str, version: str, group: str | None = None) -> None: ...
    def is_installed(self, package: str) -> Package: ...
    def get_package(self, package: str) -> Package: ...

    def apply_codemod(self, module: str, codemod) -> None: ...

    def prompt(self, message: str) -> bool:
        return False

    def ask(self, question: str) -> str:
        return ""

    def interview(self, questions: list[Question]) -> dict[str, str]:
        return {}

    def echo(self, message: str) -> None: ...


class Generator:
    id: typing.ClassVar[str]
    description: typing.ClassVar[str]

    def generate(self, ctx: Context) -> None: ...
