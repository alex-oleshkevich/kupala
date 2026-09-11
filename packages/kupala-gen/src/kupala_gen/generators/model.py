import click


@click.command("model")
def generator() -> None:
    click.echo("model")
