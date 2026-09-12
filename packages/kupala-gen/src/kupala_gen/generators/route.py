import click


@click.command("route")
def generator() -> None:
    """Generate a route."""

    click.echo("route")
