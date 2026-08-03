import jinja2

from demo.demo.config import settings
from kupala.applications import Kupala
from kupala.requests import Request
from kupala.responses import Response, response
from kupala.routing import Routes
from kupala.templates import JinjaTemplates

routes = Routes()


@routes.get("/")
async def index_view(request: Request) -> Response:
    return response(request).template(200, "index.html.j2")


app = Kupala(
    debug=True,
    routes=routes,
    settings=settings,
    templates=JinjaTemplates(
        jinja2.Environment(
            autoescape=True,
            loader=jinja2.PackageLoader("demo"),
        )
    ),
)
