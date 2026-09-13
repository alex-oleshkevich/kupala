import typing

from pydantic import BaseModel

from demo.dependencies import ProductCatalog
from demo.security import DemoAPIKey, DemoBasicIdentity
from kupala.api import APIExtension, DocsOptions
from kupala.errors import NotFoundError
from kupala.params import Body, Form, Query
from kupala.requests import Request
from kupala.responses import JSONResponse, Response, response
from kupala.routing import Routes
from kupala.schema.openapi import Info, OpenAPI, Operation

routes = Routes(tags=["products"])


class Product(BaseModel):
    sku: str
    name: str


class ProductHeaders(typing.TypedDict, total=False):
    Location: str
    XRequestId: str


@routes.get("/products", name="products.index")
async def list_products(
    request: Request,
    catalog: ProductCatalog,
    q: Query[str | None] = None,
) -> JSONResponse[list[Product]]:
    """List the catalog.

    Pass `q` to match on either sku or name. The whole catalog comes back when it is absent.
    """

    matches = [
        Product(sku=sku, name=name)
        for sku, name in catalog.products.items()
        if q is None or q.lower() in f"{sku} {name}".lower()
    ]
    return JSONResponse([product.model_dump(mode="json") for product in matches])


@routes.get("/basic", name="security.basic")
async def basic_auth(identity: DemoBasicIdentity) -> JSONResponse[str]:
    return JSONResponse(identity.principal)


@routes.get("/products/{sku}", name="products.show")
async def show_product(
    request: Request,
    catalog: ProductCatalog,
) -> JSONResponse[Product, typing.Literal[200], ProductHeaders]:
    """Fetch one product by its sku."""

    # nothing binds a path parameter to an argument yet, so the view reads it itself
    sku = request.path_params["sku"]
    if sku not in catalog.products:
        # the sku came from the url, and reflecting request data into a response is how it reaches a log
        raise NotFoundError("No product with that sku.")

    product = Product(sku=sku, name=catalog.products[sku])
    return JSONResponse(product.model_dump(mode="json"), headers={"XRequestId": sku})


@routes.delete(
    "/products/{sku}",
    name="products.destroy",
    openapi=Operation(summary="Withdraw a product", deprecated=True),
)
async def delete_product(request: Request, catalog: ProductCatalog, _api_key: DemoAPIKey) -> Response:
    catalog.products.pop(request.path_params["sku"], None)
    return response(request).empty()


@routes.get("/products/search")
async def search_product(request: Request, q: Query[str] | None = None) -> Response:
    """Search a product.

    Find a good product."""
    return response(request).empty()


class CreateProductInput(BaseModel):
    name: str
    sku: str


@routes.post("/products", name="products.create", openapi=Operation(summary="Create a product"))
async def create_product(
    request: Request,
    body: Body[CreateProductInput],
) -> JSONResponse[CreateProductInput, typing.Literal[201], ProductHeaders]:
    return JSONResponse[CreateProductInput, typing.Literal[201], ProductHeaders](
        body.model_dump(mode="json"),
        status_code=201,
        headers={"Location": f"/products/{body.sku}"},
    )


class UpdateProductInput(BaseModel):
    name: str
    sku: str


@routes.put("/products", name="products.update", openapi=Operation(summary="Update a product"))
async def update_product(
    request: Request,
    kek: Form[str],
    body: Form[CreateProductInput],
) -> JSONResponse[CreateProductInput, typing.Literal[200], ProductHeaders]:
    return JSONResponse[CreateProductInput, typing.Literal[200], ProductHeaders](
        body.model_dump(mode="json"),
        headers={"XRequestId": body.sku},
    )


api = APIExtension(
    "/api/v1",
    namespace="api",
    routes=routes,
    openapi=OpenAPI(
        info=Info(
            title="Demo API",
            version="1.0.0",
            summary="The catalog, described by the routes that serve it.",
        )
    ),
    docs=DocsOptions(
        openapi_path="/openapi.json",
        swagger_path="/docs",
        redoc_path="/redoc",
        scalar_path="/scalar",
    ),
)
