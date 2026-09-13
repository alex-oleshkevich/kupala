from demo.dependencies import Currency, ProductCatalog
from demo.security import DemoBasicIdentity
from kupala.middleware import CallNext
from kupala.requests import Request
from kupala.responses import Response, response


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


async def require_basic_auth(
    request: Request,
    call_next: CallNext,
    /,
    _identity: DemoBasicIdentity,
) -> Response:
    return await call_next(request)


# middleware is invoked through the injector, exactly like an endpoint: everything after `/` is
# resolved by type. The catalog here is the very same object the endpoint below receives.
async def catalog_header_middleware(
    request: Request,
    call_next: CallNext,
    /,
    catalog: ProductCatalog,
    currency: Currency,
) -> Response:
    response = await call_next(request)
    response.headers["x-catalog-size"] = str(len(catalog.products))
    response.headers["x-currency"] = currency
    return response


# a middleware that answers by itself simply never calls the continuation it was handed
async def maintenance_guard(request: Request, call_next: CallNext, /, currency: Currency) -> Response:
    return response(request).json(
        {"detail": "The catalog is briefly offline.", "currency": currency},
        status_code=503,
    )
