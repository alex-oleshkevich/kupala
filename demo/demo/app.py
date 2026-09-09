from demo.api import api
from demo.commands import commands
from demo.lifespans import announce, open_catalog
from demo.middleware import app_middleware, example_middleware
from demo.views import routes
from kupala.applications import Kupala

app = Kupala(
    __name__,
    debug=True,
    routes=routes,
    middleware=[app_middleware, example_middleware],
    lifespans=[announce, open_catalog],
    commands=commands,
    extensions=[api],
)
