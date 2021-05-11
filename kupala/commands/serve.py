import click
import uvicorn


@click.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Bind socket to this host.",
    show_default=True,
)
@click.option(
    "--port",
    type=int,
    default=7000,
    help="Bind socket to this port.",
    show_default=True,
)
@click.option(
    "--debug",
    type=bool,
    default=False,
    help="Run application in debug mode.",
    show_default=True,
    is_flag=True,
)
@click.argument("app", default="kupala_demo.app:app")
def serve(host: str, port: int, app: str, debug: bool) -> None:
    uvicorn.run(app, host=host, port=port, reload=debug, debug=debug)
