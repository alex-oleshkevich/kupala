import typing

from kupala.http import Request


class ContextProcessor(typing.Protocol):  # pragma: nocover
    def __call__(self, request: Request) -> typing.Mapping | typing.Awaitable[typing.Mapping]:
        ...
