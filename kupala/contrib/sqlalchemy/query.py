import sqlalchemy as sa
import typing
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import TypedReturnsRows

from kupala.choices import Choices
from kupala.collection import Collection
from kupala.pagination import Page

_ROW = typing.TypeVar("_ROW", bound=typing.Any)


class Query:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @typing.overload
    async def one(self, stmt: TypedReturnsRows[_ROW]) -> _ROW:  # pragma: no cover
        ...

    @typing.overload
    async def one(self, stmt: sa.Executable) -> typing.Any:  # pragma: no cover
        ...

    async def one(self, stmt: sa.Executable) -> typing.Any:
        result = await self.session.scalars(stmt)
        return result.one()

    @typing.overload
    async def one_or_none(self, stmt: TypedReturnsRows[_ROW]) -> _ROW | None:  # pragma: no cover
        ...

    @typing.overload
    async def one_or_none(self, stmt: sa.Executable) -> typing.Any | None:  # pragma: no cover
        ...

    async def one_or_none(self, stmt: sa.Executable) -> typing.Any | None:
        result = await self.session.scalars(stmt)
        return result.one_or_none()

    @typing.overload
    async def one_or_default(
        self, stmt: TypedReturnsRows[_ROW], default_object: typing.Any
    ) -> _ROW:  # pragma: no cover
        ...

    @typing.overload
    async def one_or_default(self, stmt: sa.Executable, default_object: typing.Any) -> typing.Any:  # pragma: no cover
        ...

    async def one_or_default(self, stmt: sa.Executable, default_object: typing.Any) -> typing.Any:
        result = await self.session.scalars(stmt)
        return result.one_or_none() or default_object

    @typing.overload
    async def one_or_raise(self, stmt: TypedReturnsRows[_ROW], exc: BaseException) -> _ROW:  # pragma: no cover
        ...

    @typing.overload
    async def one_or_raise(self, stmt: sa.Executable, exc: BaseException) -> typing.Any:  # pragma: no cover
        ...

    async def one_or_raise(self, stmt: sa.Executable, exc: BaseException) -> typing.Any:
        result = await self.one_or_none(stmt)
        if result is None:
            raise exc
        return result

    @typing.overload
    async def all(self, stmt: TypedReturnsRows[_ROW]) -> Collection[_ROW]:  # pragma: no cover
        ...

    @typing.overload
    async def all(self, stmt: sa.Executable) -> Collection[typing.Any]:  # pragma: no cover
        ...

    async def all(self, stmt: sa.Executable) -> Collection[typing.Any]:
        result = await self.session.scalars(stmt)
        return Collection(result.all())

    @typing.overload
    async def iterator(
        self, stmt: TypedReturnsRows[_ROW], batch_size: int = 1000
    ) -> typing.AsyncGenerator[_ROW, None]:  # pragma: no cover
        yield  # type: ignore[misc]

    @typing.overload
    async def iterator(
        self, stmt: sa.Executable, batch_size: int = 1000
    ) -> typing.AsyncGenerator[typing.Any, None]:  # pragma: no cover
        yield

    async def iterator(self, stmt: sa.Executable, batch_size: int = 1000) -> typing.AsyncGenerator[typing.Any, None]:
        stmt = stmt.execution_options(yield_per=batch_size)
        result = await self.session.stream(stmt)
        async for partition in result.partitions(batch_size):
            for row in partition:
                yield row[0]

    async def exists(self, stmt: sa.Select) -> bool:
        stmt = sa.select(sa.exists(stmt))
        result = await self.session.scalars(stmt)
        return result.one() is True

    async def count(self, stmt: typing.Any) -> int:
        stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
        result = await self.session.scalars(stmt)
        count = result.one()
        return int(count) if count else 0

    @typing.overload
    async def paginate(
        self, stmt: TypedReturnsRows[_ROW], page: int = 1, page_size: int = 50
    ) -> Page[_ROW]:  # pragma: no cover
        ...

    @typing.overload
    async def paginate(
        self, stmt: sa.Executable, page: int = 1, page_size: int = 50
    ) -> Page[typing.Any]:  # pragma: no cover
        ...

    async def paginate(self, stmt: sa.Executable, page: int = 1, page_size: int = 50) -> Page[typing.Any]:
        stmt = typing.cast("sa.Select", stmt)
        offset = (page - 1) * page_size
        total = await self.count(stmt)
        rows = await self.all(stmt.limit(page_size).offset(offset))
        return Page(list(rows), total, page, page_size)

    async def choices(
        self,
        stmt: sa.Executable,
        label_attr: str | typing.Callable = "name",
        value_attr: str | typing.Callable = "id",
    ) -> Choices:
        rows = await self.all(stmt)
        return Collection(rows).choices(label_attr=label_attr, value_attr=value_attr)


query = Query
