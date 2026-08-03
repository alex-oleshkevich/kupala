import typing

from kupala.routing import Route
from kupala.templates import Templates


class Kupala:
    def __init__(
        self,
        *,
        routes: typing.Sequence[Route],
        debug: bool = False,
        templates: Templates | None = None,
    ) -> None:
        self.routes = routes
        self.debug = debug
        self.templates = templates
