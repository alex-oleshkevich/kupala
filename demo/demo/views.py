import datetime
import decimal
import itertools
import json
import typing
import uuid

import anyio

from demo.dependencies import Currency, CurrentCustomer, Orders, ProductCatalog
from demo.middleware import catalog_header_middleware, maintenance_guard
from demo.models import Sort
from kupala.errors import BadRequestError
from kupala.params import Query, QueryParam
from kupala.requests import Request
from kupala.responses import Response, ServerSentEvent, response
from kupala.routing import Routes

routes = Routes()


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


@routes.get("/catalog", middleware=[catalog_header_middleware])
async def catalog_view(request: Request, catalog: ProductCatalog) -> Response:
    return response(request).json(catalog.products)


@routes.get("/catalog/offline", middleware=[maintenance_guard])
async def catalog_offline_view(request: Request) -> Response:
    raise AssertionError("the guard answers before this runs")


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
