from __future__ import annotations

import re
import typing as t
from imia import UserToken
from starlette import requests
from starlette.requests import empty_receive, empty_send
from starlette.types import Receive, Scope, Send
from starsessions import Session

if t.TYPE_CHECKING:
    from .application import Kupala


class Request(requests.Request):
    def __new__(cls, scope: Scope, receive: Receive = empty_receive, send: Send = empty_send) -> Request:
        if 'request' not in scope:
            instance = super().__new__(cls)
            instance.__init__(scope, receive, send)
            scope['request'] = instance
        return scope['request']

    @property
    def app(self) -> 'Kupala':
        return self.scope['app']

    @property
    def auth(self) -> UserToken:
        assert "auth" in self.scope, "AuthenticationMiddleware must be installed to access request.auth"
        return self.scope["auth"]

    @property
    def wants_json(self) -> bool:
        """Test if request sends Accept header
        with 'application/json' value."""
        return "application/json" in self.headers.get("accept", "")

    @property
    def is_xhr(self) -> bool:
        """
        Is true when the request is a XMLHttpRequest.
        It works if JavaScript's HTTP client sets an X-Requested-With HTTP header.
        Known frameworks:
        http://en.wikipedia.org/wiki/List_of_Ajax_frameworks#JavaScript
        :return:
        """
        return self.headers.get("x-requested-with", None) == "XMLHttpRequest"

    @property
    def ip(self) -> str:
        """Returns the IP address of user."""
        return self.client.host

    @property
    def secure(self) -> bool:
        """Determine if the request served over SSL."""
        return self.scope["scheme"] == "https"

    @property
    def is_post(self) -> bool:
        """Test if request was made using POST command."""
        return self.method.upper() == "POST"

    @property
    def session(self) -> Session:
        assert "session" in self.scope, "SessionMiddleware must be installed to access request.session"
        return self.scope['session']

    def url_matches(self, *patterns: t.Union[str, t.Pattern]) -> bool:
        for pattern in patterns:
            if pattern == self.url.path:
                return True
            if re.match(pattern, self.url.path):
                return True
        return False

    def full_url_matches(self, *patterns: t.Union[str, t.Pattern]) -> bool:
        for pattern in patterns:
            if pattern == str(self.url):
                return True
            if re.match(pattern, str(self.url)):
                return True
        return False
