import dataclasses
import typing

import jinja2
from starlette.types import Lifespan

from kupala.binders import ModelBinder
from kupala.commands import Commands
from kupala.error_handlers import ErrorHandler
from kupala.routing import Routes
from kupala.templates import ContextProcessor, JinjaFilters, JinjaGlobals

if typing.TYPE_CHECKING:
    from kupala.applications import Kupala


@dataclasses.dataclass
class AppBuilder:
    """What an extension may contribute to the application being built.

    Every field is a container an extension appends to in place, so several extensions add to the
    same builder without overwriting one another. Middleware is deliberately absent: its order is a
    security boundary, so the application places it and nothing installs it behind your back.
    """

    routes: Routes = dataclasses.field(default_factory=Routes)
    commands: Commands = dataclasses.field(default_factory=Commands)
    lifespans: list[Lifespan[Kupala]] = dataclasses.field(default_factory=list)
    template_loaders: list[jinja2.BaseLoader] = dataclasses.field(default_factory=list)
    template_globals: JinjaGlobals = dataclasses.field(default_factory=dict)
    template_filters: JinjaFilters = dataclasses.field(default_factory=dict)
    model_binders: list[ModelBinder] = dataclasses.field(default_factory=list)
    context_processors: list[ContextProcessor] = dataclasses.field(default_factory=list)
    error_handlers: dict[type[Exception], ErrorHandler] = dataclasses.field(default_factory=dict)


class Extension(typing.Protocol):
    def install(self, builder: AppBuilder) -> None: ...
