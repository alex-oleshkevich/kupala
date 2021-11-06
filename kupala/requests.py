from __future__ import annotations

import re
import typing as t
from imia import UserToken
from starlette import requests
from starlette.datastructures import UploadFile
from starlette.requests import empty_receive, empty_send
from starlette.types import Receive, Scope, Send
from starsessions import Session

if t.TYPE_CHECKING:
    from .application import Kupala


class OldFormInput(t.Mapping):
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, key: str, default: t.Any = None) -> t.Any:
        return self._data.get(key, default)

    def __getitem__(self, item: str) -> t.Any:
        return self._data[item]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> t.Iterator[t.Tuple[str, t.Any]]:
        return iter(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def to_json(self) -> dict:
        return self._data


class FormErrors:
    def __init__(self, errors: t.Mapping, error_message: str) -> None:
        self._errors = errors
        self._error_message = error_message

    def to_json(self) -> dict:
        return {
            'message': self._error_message,
            'field_errors': self._errors,
        }

    def __bool__(self) -> bool:
        return bool(self._errors or self._error_message)


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

    @property
    def old_input(self) -> OldFormInput:
        """Get previous form input. This value does not include uploaded files."""
        return OldFormInput(self.session.pop('_form_old_input', {}))

    async def remember_form_data(self) -> None:
        """Flush current form data into session so it can be used on the next page to render form errors."""
        data = await self.form()
        self.session['_form_old_input'] = {k: v for k, v in data.items() if not isinstance(v, UploadFile)}

    @property
    def form_errors(self) -> FormErrors:
        """Get form errors generated on the previous page."""
        return FormErrors(
            errors=self.session.pop('_form_field_errors'),
            error_message=self.session.pop('_form_error'),
        )

    def set_form_errors(self, error_message: str = '', field_errors: dict = None) -> None:
        """Flush form error message and form field errors into session.
        This data can be later retrieved via `request.form_errors` attribute."""
        self.session['_form_error'] = error_message
        self.session['_form_field_errors'] = field_errors or {}

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
