from starlette.authentication import AuthCredentials, AuthenticationBackend, BaseUser
from starlette.requests import HTTPConnection


class DummyBackend(AuthenticationBackend):
    def __init__(self, user: BaseUser | None) -> None:
        self.user = user

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        if self.user:
            return AuthCredentials(), self.user
        return None
