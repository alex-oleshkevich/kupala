import contextlib
import dataclasses
import decimal
import itertools
import json
import typing

import anyio

from kupala.applications import Kupala
from kupala.dependencies import Factory, FromState, Value
from kupala.errors import BadRequestError
from kupala.middleware import CallNext
from kupala.requests import Request
from kupala.responses import Response, ServerSentEvent, response
from kupala.routing import Routes

routes = Routes()


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


class DemoApp(Kupala):
    @contextlib.asynccontextmanager
    async def lifespan(self, app: typing.Self) -> typing.AsyncGenerator[dict[str, typing.Any]]:
        yield {"catalog": Catalog()}


app = DemoApp(
    __name__,
    debug=True,
    routes=routes,
    middleware=[app_middleware, example_middleware],
)
