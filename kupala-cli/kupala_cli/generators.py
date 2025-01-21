import dataclasses
import hashlib
import importlib
import logging
import os
import tempfile
import typing

import jinja2


@dataclasses.dataclass
class Context:
    project_name: str
    project_directory: str
    python_version: str
    kupala_version: str
    kupala_cli_version: str


class GeneratorError(Exception):
    pass


class Generator:
    logger = logging.getLogger(__name__)

    def generate(self, context: Context) -> None:
        raise NotImplementedError

    def iter_directory(self, directory: str) -> typing.Iterator[str]:
        for root, dirs, files in os.walk(directory):
            for file in files:
                yield os.path.join(root, file)

    def render_templates(
        self,
        context: Context,
        variables: dict[str, typing.Any] | None = None,
    ) -> None:
        variables = variables or {}
        variables.update(dataclasses.asdict(context))

        self_module = self.__class__.__module__
        instance = importlib.import_module(self_module)
        module_path = os.path.dirname(str(instance.__file__))
        templates_path = os.path.join(module_path, "templates")
        if not os.path.exists(templates_path):
            raise GeneratorError(f"Templates directory not found: {templates_path}")

        env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_path))
        with tempfile.TemporaryDirectory(delete=True) as temp_dir:
            self.logger.debug(f"Rendering template into temporary directory: {temp_dir}.")

            for path in self.iter_directory(templates_path):
                source_name = path.removeprefix(templates_path + os.sep)
                target_name = env.from_string(source_name).render(variables).removesuffix(".jinja2")
                relative_target_name = target_name.removeprefix(context.project_name + os.sep)

                os.makedirs(
                    os.path.join(temp_dir, os.path.dirname(relative_target_name)),
                    exist_ok=True,
                )
                env.get_template(source_name).stream(variables).dump(os.path.join(temp_dir, relative_target_name))
                self.logger.debug(f"Rendered: {source_name} -> {target_name}")

            self.logger.debug(f"Generated files in {temp_dir}.")
            self.copy_directory(temp_dir, context.project_directory)

    def copy_directory(self, source: str, target: str) -> None:
        self.logger.debug(f'Copying directory {source} to "{target}"')
        for path in self.iter_directory(source):
            self.copy_file(path, os.path.join(target, path.removeprefix(source + os.sep)))

    def copy_file(self, source: str, target: str) -> None:
        self.logger.debug(f"Copying file: {source} -> {target}")

        # if os.path.exists(target):
        #     self.logger.debug(
        #         f"File already exists: {target}. Comparing file contents."
        #     )
        #     is_same, diff = self.diff_files(source, target)
        #     if is_same:
        #         self.logger.debug("Files are identical. Skipping.")
        #         return

        #     self.logger.debug("Files are different. Overwriting.")

        target_dir = os.path.dirname(target)
        os.makedirs(target_dir, exist_ok=True)
        if os.path.isdir(source):
            self.logger.debug(f"Creating directory: {target_dir}")
            return

        with open(source, "rb") as source_f, open(target, "wb") as target_f:
            while chunk := source_f.read(1024):
                target_f.write(chunk)

    def diff_files(self, source: str, target: str) -> tuple[bool, str]:
        source_hasher = hashlib.md5()
        target_hasher = hashlib.md5()
        with open(source, "rb") as source_f:
            with open(target, "wb") as target_f:
                while chunk := source_f.read():
                    source_hasher.update(chunk)

                while chunk := target_f.read():
                    target_hasher.update(chunk)

                source_hash = source_hasher.hexdigest()
                target_hash = target_hasher.hexdigest()
                if source_hash == target_hash:
                    return True, ""
        return False, ""
