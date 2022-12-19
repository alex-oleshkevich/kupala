from __future__ import annotations

import typing
from starlette import requests
from starlette.requests import empty_receive, empty_send
from starlette.types import Receive, Scope, Send

from kupala.authentication import AnonymousUser, AuthToken, LoginState


class QueryParams(requests.QueryParams):
    def get_bool(self, key: str, default: bool | None = None) -> bool | None:
        value = self.get(key, None)
        return value.lower() in ["t", "true", "yes", "on", "1"] if value is not None else default

    def get_list(self, key: str, subcast: typing.Callable | None = None) -> list[str]:
        items = self.getlist(key)
        if subcast:
            return list(map(subcast, items))
        return items

    def get_int(self, key: str, default: int | None = None) -> typing.Optional[int]:
        value: str = self.get(key, "")
        return int(value) if value != "" and value.isnumeric() else default


class CachedBodyMixin:
    def __new__(cls, scope: Scope, receive: Receive = empty_receive, send: Send = empty_send) -> Request:
        if "request" not in scope:
            instance = super().__new__(cls)
            instance.__init__(scope, receive, send)  # type: ignore
            scope["request"] = instance
        elif scope["request"].__class__ != cls:
            # view function uses custom request class
            request = scope["request"]
            request.__class__ = cls
            scope["request"] = request
        return scope["request"]


class Request(requests.Request, CachedBodyMixin):
    @property
    def query_params(self) -> QueryParams:
        return QueryParams(super().query_params)

    @property
    def auth(self) -> AuthToken:
        return self.scope.get("auth", AuthToken(user=AnonymousUser(), state=LoginState.ANONYMOUS))

    @property
    def user(self) -> typing.Any:
        return self.auth.user

    @property
    def secure(self) -> bool:
        """Determine if the request served over SSL."""
        return self.scope["scheme"] == "https"

    @property
    def is_submitted(self) -> bool:
        return self.method.lower() in ["post", "put", "patch", "delete"]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.method} {self.url}>"
