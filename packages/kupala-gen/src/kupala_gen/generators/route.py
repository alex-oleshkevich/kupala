import click


@click.command("route")
def generator() -> None:
    click.echo("route")
