import logging
import click

from kupala_cli.commands.new import new_command
from kupala_cli.commands.add import add_command
from kupala_cli.plugins import discover_plugins

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)


@click.group()
@click.option("--verbose", is_flag=True)
def app(verbose: bool) -> None:
    if verbose:
        logging.getLogger(__name__.split(".")[0]).setLevel(logging.DEBUG)


def main() -> None:
    for plugin in discover_plugins("kupala.plugin"):
        plugin(app)

    app.add_command(new_command)
    app.add_command(add_command)

    app()


if __name__ == "__main__":
    main()
