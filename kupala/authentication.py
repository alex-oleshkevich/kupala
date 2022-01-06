from __future__ import annotations

import abc
import typing

import imia
from imia.authentication import APIKeyAuthenticator, BaseAuthenticator, BearerAuthenticator, HTTPBasicAuthenticator, \
    SessionAuthenticator, TokenAuthenticator
from imia.impersonation import exit_impersonation, get_original_user, impersonate, impersonation_is_active
from imia.login import get_session_auth_hash, get_session_auth_id, login_user
from imia.protocols import Authenticator, UserLike
from imia.user_providers import InMemoryProvider, UserProvider
from imia.user_token import AnonymousUser, LoginState

from kupala.requests import Request

__all__ = [
    'LoginManager', 'UserLike', 'Authenticator', 'UserToken', 'InMemoryProvider', 'UserProvider',
    'BaseAuthenticator', 'BaseUser', 'BearerAuthenticator', 'TokenAuthenticator', 'SessionAuthenticator',
    'HTTPBasicAuthenticator', 'APIKeyAuthenticator', 'impersonate', 'impersonation_is_active', 'exit_impersonation',
    'get_original_user', 'get_session_auth_id', 'get_session_auth_hash', 'login_user', 'AnonymousUser', 'LoginState',
]


class LoginManager(imia.LoginManager):
    @classmethod
    def from_request(cls, request: Request) -> LoginManager:
        return request.app.auth.login_manager


class UserToken(imia.UserToken):
    @classmethod
    def from_request(cls, request: Request) -> UserToken:
        return request.auth


class BaseUser(abc.ABC):  # pragma: nocover
    @abc.abstractmethod
    def get_id(self) -> typing.Any:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_display_name(self) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_scopes(self) -> list[str]:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_hashed_password(self) -> str:
        raise NotImplementedError()
