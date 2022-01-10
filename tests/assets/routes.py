from kupala.requests import Request
from kupala.responses import JSONResponse
from kupala.routing import Routes


def view(request: Request) -> JSONResponse:
    return JSONResponse({})


def configure(routes: Routes) -> None:
    routes.add('/callback-included', view)
