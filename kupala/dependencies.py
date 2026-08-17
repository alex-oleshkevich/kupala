from __future__ import annotations

import functools
import typing


class HasResolver(typing.Protocol):
    resolver: DependencyResolver


class BoundCallable[R](typing.Protocol):
    def __call__(self, **overrides: typing.Any) -> R: ...


class DependencyResolver:
    async def invoke[**P, R](
        self,
        fn: typing.Callable[P, typing.Awaitable[R]],
        *_args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        if _args:
            raise TypeError("Positional arguments are not supported.")

        wrapped = self.bind(fn)
        return await wrapped(**kwargs)

    def bind[**P, R](self, fn: typing.Callable[P, R]) -> BoundCallable[R]:
        return functools.partial(fn)

    @classmethod
    def of(cls, source: HasResolver) -> DependencyResolver:
        return source.resolver
