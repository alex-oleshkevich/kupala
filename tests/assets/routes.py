from kupala.http import route
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from kupala.http.routing import Routes


@route("/callback-included")
def view(request: Request) -> JSONResponse:
    return JSONResponse({})


def configure(routes: Routes) -> None:
    routes.add(view)
