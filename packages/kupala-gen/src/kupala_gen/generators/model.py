import click


@click.command("model")
def generator() -> None:
    """Generate a model."""

    click.echo("model")
