from __future__ import annotations

import jinja2
import typing

from kupala.http.requests import Request


class ContextProcessor(typing.Protocol):  # pragma: nocover
    def __call__(self, request: Request) -> typing.Mapping | typing.Awaitable[typing.Mapping]:
        ...


class DynamicChoiceLoader(jinja2.ChoiceLoader):
    loaders: list

    def add_loader(self, loader: jinja2.BaseLoader) -> None:
        # don't touch the first loader, this is usually project's template directory
        # also, don't append it because the last loader should be one that loads templates from the framework
        self.loaders.insert(1, loader)
