from __future__ import annotations

import typing

import sqlalchemy as sa
from starlette_sqlalchemy import Collection
from starlette_sqlalchemy import Query as BaseQuery

from kupala.contrib.sqlalchemy.models import Base

M = typing.TypeVar("M", bound=Base)


class Query(BaseQuery):
    async def select_all(
        self,
        model_class: type[M],
        *,
        filters: typing.Mapping[str, typing.Any] | None = None,
        joins: typing.Sequence[sa.Join] | None = None,
        where: sa.ClauseElement | None = None,
        group_by: sa.Column | None = None,
        order_by: sa.Column | None = None,
        limit: int | None = None,
        offset: int | None = None,
        options: typing.Sequence[typing.Any] | None = None,
    ) -> Collection[M]:
        stmt = sa.select(model_class)
        if filters:
            stmt = stmt.filter_by(**filters)
        if joins:
            for join in joins:
                stmt = stmt.join(join)
        if where:
            stmt = stmt.where(where)
        if group_by:
            stmt = stmt.group_by(group_by)
        if order_by:
            stmt = stmt.order_by(order_by)
        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        if options:
            stmt = stmt.options(*options)
        return await self.all(stmt)

    async def select_one(
        self,
        model_class: type[M],
        *,
        filters: typing.Mapping[str, typing.Any] | None = None,
        joins: typing.Sequence[sa.Join] | None = None,
        where: sa.ClauseElement | None = None,
        group_by: sa.Column | None = None,
        order_by: sa.Column | None = None,
        limit: int | None = None,
        offset: int | None = None,
        options: typing.Sequence[typing.Any] | None = None,
    ) -> M:
        pass

    async def select_one_or_none(
        self,
        model_class: type[M],
        *,
        filters: typing.Mapping[str, typing.Any] | None = None,
        joins: typing.Sequence[sa.Join] | None = None,
        where: sa.ClauseElement | None = None,
        group_by: sa.Column | None = None,
        order_by: sa.Column | None = None,
        limit: int | None = None,
        offset: int | None = None,
        options: typing.Sequence[typing.Any] | None = None,
    ) -> M | None:
        pass


query = Query
