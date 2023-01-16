import sqlalchemy as sa
from starlette.authentication import BaseUser
from starlette.requests import HTTPConnection


class UserLoader:
    def __init__(self, user_model_class: type, pk_column: str = "id") -> None:
        self.model_class = user_model_class
        self.pk_column = pk_column

    async def __call__(self, connection: HTTPConnection, user_id: str) -> BaseUser | None:
        column = getattr(self.model_class, self.pk_column)
        stmt: sa.Executable = sa.select(self.model_class).where(column == int(user_id))
        result = await connection.state.db.scalars(stmt)
        return result.one_or_none()
