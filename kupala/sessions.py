import abc
import typing as t
import uuid
from base64 import b64decode, b64encode

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from starlette.datastructures import MutableHeaders, Secret
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala import json


class SessionError(Exception):
    ...


class SessionNotLoaded(SessionError):
    pass


class SessionBackend(abc.ABC):
    """Base class for session backends."""

    @abc.abstractmethod
    async def read(self, session_id: str) -> t.Dict[str, t.Any]:  # pragma: no cover
        """Read session data from the storage."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def write(
        self, data: t.Dict, session_id: t.Optional[str] = None
    ) -> str:  # pragma: no cover
        """Write session data to the storage."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def remove(self, session_id: str) -> None:  # pragma: no cover
        """Remove session data from the storage."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def exists(self, session_id: str) -> bool:  # pragma: no cover
        """Test if storage contains session data for a given session_id."""
        raise NotImplementedError()

    async def generate_id(self) -> str:
        """Generate a new session id."""
        return str(uuid.uuid4())


class CookieBackend(SessionBackend):
    """Stores session data in the browser's cookie as a signed string."""

    def __init__(self, secret_key: t.Union[str, Secret], max_age: int):
        self._signer = TimestampSigner(str(secret_key))
        self._max_age = max_age

    async def read(self, session_id: str) -> t.Dict:
        """A session_id is a signed session value."""
        try:
            data = self._signer.unsign(session_id, max_age=self._max_age)
            return json.loads(b64decode(data).decode())
        except (BadSignature, SignatureExpired):
            return {}

    async def write(self, data: t.Dict, session_id: t.Optional[str] = None) -> str:
        """The data is a session id in this backend."""
        encoded_data = b64encode(json.dumps(data).encode("utf-8"))
        return self._signer.sign(encoded_data).decode("utf-8")

    async def remove(self, session_id: str) -> None:
        """Session data stored on client side - no way to remove it."""

    async def exists(self, session_id: str) -> bool:
        return False


class InMemoryBackend(SessionBackend):
    """Stores session data in a dictionary."""

    def __init__(self, data: dict = None) -> None:
        self.data: dict = data or {}

    async def read(self, session_id: str) -> t.Dict:
        return self.data.get(session_id, {}).copy()

    async def write(self, data: t.Dict, session_id: t.Optional[str] = None) -> str:
        session_id = session_id or await self.generate_id()
        self.data[session_id] = data
        return session_id

    async def remove(self, session_id: str) -> None:
        del self.data[session_id]

    async def exists(self, session_id: str) -> bool:
        return session_id in self.data


class Session:
    def __init__(self, backend: SessionBackend, session_id: str = None) -> None:
        self.session_id = session_id
        self._data: dict[str, t.Any] = {}
        self._backend = backend
        self.is_loaded = False
        self._is_modified = False

    @property
    def is_empty(self) -> bool:
        """Check if session has data."""
        return len(self.keys()) == 0

    @property
    def is_modified(self) -> bool:
        """Check if session data has been modified,"""
        return self._is_modified

    @property
    def data(self) -> dict:
        if not self.is_loaded:
            raise SessionNotLoaded("Attempt to read from not loaded session.")
        return self._data

    @data.setter
    def data(self, value: dict[str, t.Any]) -> None:
        self._data = value

    async def load(self) -> None:
        """Load data from the backend.
        Subsequent calls do not take any effect."""
        if self.is_loaded:
            return

        if not self.session_id:
            self.data = {}
        else:
            self.data = await self._backend.read(self.session_id)

        self.is_loaded = True

    async def persist(self) -> str:
        self.session_id = await self._backend.write(self.data, self.session_id)
        return self.session_id

    async def delete(self) -> None:
        if self.session_id:
            self.data = {}
            self._is_modified = True
            await self._backend.remove(self.session_id)

    async def flush(self) -> str:
        self._is_modified = True
        await self.delete()
        return await self.regenerate_id()

    async def regenerate_id(self) -> str:
        self.session_id = await self._backend.generate_id()
        self._is_modified = True
        return self.session_id

    def keys(self) -> t.KeysView[str]:
        return self.data.keys()

    def values(self) -> t.ValuesView[t.Any]:
        return self.data.values()

    def items(self) -> t.ItemsView[str, t.Any]:
        return self.data.items()

    def pop(self, key: str, default: t.Any = None) -> t.Any:
        self._is_modified = True
        return self.data.pop(key, default)

    def get(self, name: str, default: t.Any = None) -> t.Any:
        return self.data.get(name, default)

    def setdefault(self, key: str, default: t.Any) -> None:
        self._is_modified = True
        self.data.setdefault(key, default)

    def clear(self) -> None:
        self._is_modified = True
        self.data.clear()

    def update(self, *args: t.Any, **kwargs: t.Any) -> None:
        self._is_modified = True
        self.data.update(*args, **kwargs)

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def __setitem__(self, key: str, value: t.Any) -> None:
        self._is_modified = True
        self.data[key] = value

    def __getitem__(self, key: str) -> t.Any:
        return self.data[key]

    def __delitem__(self, key: str) -> None:
        self._is_modified = True
        del self.data[key]


class SessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        secret_key: t.Union[str, Secret],
        session_cookie: str = "session",
        max_age: int = 14 * 24 * 60 * 60,  # 14 days, in seconds
        same_site: str = "lax",
        https_only: bool = False,
        backend: SessionBackend = None,
    ) -> None:
        self.app = app
        self.backend = backend or CookieBackend(secret_key, max_age)
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:  # Secure flag can be used with HTTPS only
            self.security_flags += "; secure"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):  # pragma: no cover
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        session_id = connection.cookies.get(self.session_cookie, None)
        scope["session"] = Session(self.backend, session_id)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                session: Session = scope["session"]
                if session.is_modified and not session.is_empty:
                    # We have session data to persist (data was changed, cleared, etc).
                    nonlocal session_id
                    session_id = await scope["session"].persist()

                    headers = MutableHeaders(scope=message)
                    header_value = "%s=%s; path=/; Max-Age=%d; %s" % (
                        self.session_cookie,
                        session_id,
                        self.max_age,
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                elif session.is_loaded and session.is_empty:
                    # no interactions to session were done
                    headers = MutableHeaders(scope=message)
                    header_value = "%s=%s; %s" % (
                        self.session_cookie,
                        "null; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT;",
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
            await send(message)

        await scope["session"].load()
        await self.app(scope, receive, send_wrapper)
