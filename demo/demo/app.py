import contextlib
import dataclasses
import datetime
import decimal
import enum
import itertools
import json
import typing
import uuid

import anyio
import click

from kupala.applications import Kupala
from kupala.commands import Commands
from kupala.dependencies import Factory, FromState, Value
from kupala.errors import BadRequestError
from kupala.middleware import CallNext
from kupala.params import Query, QueryParam
from kupala.requests import Request
from kupala.responses import Response, ServerSentEvent, response
from kupala.routing import Routes

routes = Routes()
commands = Commands()


class Sort(enum.StrEnum):
    NEWEST = "newest"
    PRICE = "price"


@dataclasses.dataclass(frozen=True, slots=True)
class Customer:
    id: int
    name: str
    email: str


class OrderBook:
    """Stands in for a repository that has to be closed when the request ends."""

    def __init__(self) -> None:
        self.orders = {42: [decimal.Decimal("649.00"), decimal.Decimal("779.00")]}

    def lifetime_value(self, customer_id: int) -> decimal.Decimal:
        return sum(self.orders.get(customer_id, []), decimal.Decimal("0.00"))


def load_customer() -> Customer:
    """A plain factory: in a real app this would read the session."""

    return Customer(id=42, name="Marta Kowalska", email="marta@northwind.pl")


def open_order_book() -> typing.Iterator[OrderBook]:
    """A generator factory: whatever follows the yield runs after the response is sent."""

    book = OrderBook()
    try:
        yield book
    finally:
        print("ORDER BOOK CLOSED")


class Catalog:
    """Loaded once at startup and shared by every request."""

    def __init__(self) -> None:
        self.products = {"DSK-01": "Standing desk", "CHR-07": "Ergonomic chair"}


type CurrentCustomer = typing.Annotated[Customer, Factory(load_customer)]
type Orders = typing.Annotated[OrderBook, Factory(open_order_book)]
type Currency = typing.Annotated[str, Value("EUR")]
# whatever the lifespan yields lands on the state of every request
type ProductCatalog = typing.Annotated[Catalog, FromState(lambda ctx, state: state.catalog)]


async def app_middleware(request: Request, call_next: CallNext) -> Response:
    print("APP")
    response = await call_next(request)
    print("AFTER APP")
    return response


async def example_middleware(request: Request, call_next: CallNext) -> Response:
    print("APP REG")
    response = await call_next(request)
    print("AFTER APP_REG")
    return response


@routes.get("/")
@routes.get("/overview", name="overview")
async def index_view(request: Request) -> Response:
    return response(request).text("hi")


@routes.get("/dependency")
async def dependency_view(
    request: Request,
    customer: CurrentCustomer,
    orders: Orders,
    currency: Currency,
) -> Response:
    return response(request).json(
        {
            "customer": customer.name,
            "email": customer.email,
            "lifetime_value": f"{orders.lifetime_value(customer.id)} {currency}",
        }
    )


@routes.get("/catalog")
async def catalog_view(request: Request, catalog: ProductCatalog) -> Response:
    return response(request).json(catalog.products)


@routes.get("/search")
async def search_view(
    request: Request,
    q: Query[str],
    page: Query[int] = 1,
    per_page: typing.Annotated[int, QueryParam("limit")] = 20,
    sort: Query[Sort] = Sort.NEWEST,
    in_stock: Query[bool] = False,
    max_price: Query[decimal.Decimal | None] = None,
    since: Query[datetime.date | None] = None,
    trace_id: Query[uuid.UUID | None] = None,
) -> Response:
    """Every scalar a query string can carry: `q` is required, and `?limit=` feeds `per_page`."""

    return response(request).json(
        {
            "q": q,
            "page": page,
            "per_page": per_page,
            "sort": sort.value,
            "in_stock": in_stock,
            "max_price": None if max_price is None else str(max_price),
            "since": None if since is None else since.isoformat(),
            "trace_id": None if trace_id is None else str(trace_id),
        }
    )


@routes.get("/error")
async def http_error_view(request: Request) -> Response:
    raise BadRequestError()


@routes.get("/unhandled")
async def unhandled_error_view(request: Request) -> Response:
    raise ValueError("boom")


@routes.post("/post")
async def post_view(request: Request) -> Response:
    return response(request).text("ok")


@routes.get("/sse", name="sse")
async def sse_view(request: Request) -> Response:
    async def ticks() -> typing.AsyncIterator[ServerSentEvent]:
        try:
            for tick in itertools.count(1):
                yield ServerSentEvent(event="tick", id=str(tick), data=json.dumps({"tick": tick}))
                await anyio.sleep(1)
        finally:
            # the generator is closed when the browser goes away, so the stream never leaks
            print("SSE CLIENT GONE")

    return response(request).sse(ticks(), keepalive_interval=5.0)


@contextlib.asynccontextmanager
async def open_catalog(app: Kupala) -> typing.AsyncGenerator[dict[str, typing.Any]]:
    yield {"catalog": Catalog()}


@contextlib.asynccontextmanager
async def announce(app: Kupala) -> typing.AsyncGenerator[None]:
    # what an extension looks like: it contributes no state, only startup and shutdown work
    print("DEMO UP")
    try:
        yield None
    finally:
        print("DEMO DOWN")


@commands.command("catalog")
@click.option("--prefix", default="", help="Only show products whose SKU starts with this.")
def catalog_command(prefix: str, catalog: ProductCatalog) -> None:
    """List the catalog the lifespan loaded.

    `prefix` is filled by click, `catalog` by the injector - exactly as an endpoint is.
    """

    for sku, name in catalog.products.items():
        if sku.startswith(prefix):
            click.echo(f"{sku}\t{name}")


@commands.command("greet", lifespan=False)
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


app = Kupala(
    __name__,
    debug=True,
    routes=routes,
    middleware=[app_middleware, example_middleware],
    lifespans=[announce, open_catalog],
    commands=commands,
)
