import typing as t

from kupala.exceptions import MethodNotAllowed
from kupala.responses import Response


class Resource:
    async def index(self, **kwargs: t.Any) -> Response:
        raise MethodNotAllowed()

    async def new(self, **kwargs: t.Any) -> Response:
        raise MethodNotAllowed()

    async def show(self, *args: t.Any, **kwargs: t.Any) -> Response:
        raise MethodNotAllowed()

    async def edit(self, **kwargs: t.Any) -> Response:
        raise MethodNotAllowed()

    async def create(self, **kwargs: t.Any) -> Response:
        raise MethodNotAllowed()

    async def update(self, **kwargs: t.Any) -> Response:
        raise MethodNotAllowed()

    async def destroy(self, **kwargs: t.Any) -> Response:
        raise MethodNotAllowed()
