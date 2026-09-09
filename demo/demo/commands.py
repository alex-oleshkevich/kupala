import anyio
import click

from demo.dependencies import Currency, Orders, ProductCatalog
from kupala.commands import Commands

commands = Commands()


@commands.command("catalog")
@click.option("--prefix", default="", help="Only show products whose SKU starts with this.")
def catalog_command(prefix: str, catalog: ProductCatalog) -> None:
    """List the catalog the lifespan loaded.

    `prefix` is filled by click, `catalog` by the injector - exactly as an endpoint is.
    """

    for sku, name in catalog.products.items():
        if sku.startswith(prefix):
            click.echo(f"{sku}\t{name}")


@commands.command("greet", with_lifespan=False)
def greet_command() -> None:
    """A command that never starts the application, so no lifespan runs."""

    click.echo("hello from a command that skipped the lifespan")


@commands.command("ping")
async def ping_command() -> None:
    """An async command: the callback is awaited on the loop that runs the lifespan.

    A synchronous command would be dispatched to the threadpool instead.
    """

    await anyio.sleep(0.1)
    click.echo("pong")


@commands.command("lifetime-value")
@click.argument("customer_id", type=int)
async def lifetime_value_command(customer_id: int, orders: Orders, currency: Currency) -> None:
    """An async command with dependencies.

    `customer_id` comes from click, `orders` and `currency` from the injector - the same split as an
    endpoint. The order book is a generator factory, so it is closed when the command returns and
    before the lifespan shuts down.
    """

    click.echo(f"{orders.lifetime_value(customer_id)} {currency}")
