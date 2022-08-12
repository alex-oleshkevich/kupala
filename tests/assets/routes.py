from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Routes


def view(request: Request) -> JSONResponse:
    return JSONResponse({})


def configure(routes: Routes) -> None:
    routes.add("/callback-included", view)
