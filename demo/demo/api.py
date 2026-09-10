"""A documented API served beside the HTML views, with all three viewers turned on."""

from pydantic import BaseModel

from demo.dependencies import ProductCatalog
from kupala.api.extension import APIExtension, DocsOptions
from kupala.errors import NotFoundError
from kupala.openapi import Info, OpenAPI
from kupala.params import Body, Form, Query
from kupala.requests import Request
from kupala.responses import Response, response
from kupala.routing import Routes

routes = Routes(tags=["products"])


@routes.get("/products", name="products.index")
async def list_products(
    request: Request,
    catalog: ProductCatalog,
    q: Query[str | None] = None,
) -> Response:
    """List the catalog.

    Pass `q` to match on either sku or name. The whole catalog comes back when it is absent.
    """

    matches = {sku: name for sku, name in catalog.products.items() if q is None or q.lower() in f"{sku} {name}".lower()}
    return response(request).json(matches)


@routes.get("/products/{sku}", name="products.show")
async def show_product(request: Request, catalog: ProductCatalog) -> Response:
    """Fetch one product by its sku."""

    # nothing binds a path parameter to an argument yet, so the view reads it itself
    sku = request.path_params["sku"]
    if sku not in catalog.products:
        # the sku came from the url, and reflecting request data into a response is how it reaches a log
        raise NotFoundError("No product with that sku.")

    return response(request).json({"sku": sku, "name": catalog.products[sku]})


@routes.delete("/products/{sku}", name="products.destroy", summary="Withdraw a product", deprecated=True)
async def delete_product(request: Request, catalog: ProductCatalog) -> Response:
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


@routes.post("/products", name="products.create", summary="Create a product")
async def create_product(request: Request, body: Body[CreateProductInput]) -> Response:
    return response(request).empty()


class UpdateProductInput(BaseModel):
    name: str
    sku: str


@routes.put("/products", name="products.update", summary="Update a product")
async def update_product(request: Request, kek: Form[str], body: Form[CreateProductInput]) -> Response:
    return response(request).empty()


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
