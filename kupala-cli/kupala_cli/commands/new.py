import importlib.metadata
import os
import sys

import click

from kupala_cli.addons.project.generator import ProjectGenerator
from kupala_cli.generators import Context

python_version = sys.version_info


@click.group("new", help="Create a new resource.")
def new_command() -> None:
    pass


@new_command.command("project", help="Create a new project.")
@click.argument("name")
@click.option("-d", "--directory", help="Path to the project.", default=os.getcwd())
@click.option("-f", "--force", help="Force overwrite existing project.", is_flag=True)
@click.option(
    "--python",
    help="Python version.",
    default=f"{python_version.major}.{python_version.minor}",
)
def new_project_command(name: str, directory: str, force: bool, python: str) -> None:
    """Initialize a new project."""
    directory = os.path.join(directory, name)
    if os.path.exists(directory) and not force:
        message = "Directory {directory} is not empty, do you want to overwrite it?".format(
            directory=click.style(directory, fg="green")
        )
        if not click.confirm(message):
            return

    os.makedirs(directory, exist_ok=True)
    context = Context(
        project_name=name,
        python_version=python,
        project_directory=directory,
        kupala_version=importlib.metadata.version("kupala"),
        kupala_cli_version=importlib.metadata.version("kupala-cli"),
    )

    generator = ProjectGenerator(name)
    generator.generate(context)
