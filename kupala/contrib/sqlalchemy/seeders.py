from __future__ import annotations

import abc
from sqlalchemy.ext.asyncio import AsyncSession


class Seeder:
    @abc.abstractmethod
    async def seed(self, session: AsyncSession) -> None:
        ...

    async def call(self, seeder_class: type[Seeder], session: AsyncSession) -> None:
        seeder = seeder_class()
        await seeder.seed(session)
