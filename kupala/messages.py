import abc
import enum
import typing as t
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.requests import Request

SCOPE_KEY = 'flash_messages'
SESSION_KEY = 'flash_messages'


class MessageCategory(enum.Enum):
    DEBUG = 'debug'
    INFO = 'info'
    SUCCESS = 'success'
    WARNING = 'warning'
    ERROR = 'error'


class FlashMessage(t.TypedDict):
    category: str
    message: str


class FlashBag:
    Category = MessageCategory

    def __init__(self, messages: t.List[FlashMessage] = None):
        self._messages = messages or []

    def add(self, message: str, category: t.Union[MessageCategory, str]) -> None:
        if isinstance(category, MessageCategory):
            category = category.value
        self._messages.append({'category': category, 'message': message})

    def debug(self, message: str) -> None:
        self.add(message, MessageCategory.DEBUG)

    def info(self, message: str) -> None:
        self.add(message, MessageCategory.INFO)

    def success(self, message: str) -> None:
        self.add(message, MessageCategory.SUCCESS)

    def warning(self, message: str) -> None:
        self.add(message, MessageCategory.WARNING)

    def error(self, message: str) -> None:
        self.add(message, MessageCategory.ERROR)

    def all(self) -> t.List[FlashMessage]:
        return self._messages

    def stream(self) -> t.Generator[FlashMessage, None, None]:
        while len(self._messages):
            yield self._messages.pop(0)

    def clear(self) -> None:
        self._messages = []

    def __len__(self) -> int:
        return len(self._messages)


class MessageStorage(abc.ABC):  # pragma: nocover
    @abc.abstractmethod
    def load(self, scope: Scope) -> FlashBag:
        raise NotImplementedError()

    @abc.abstractmethod
    def save(self, scope: Scope, bag: FlashBag) -> None:
        raise NotImplementedError()


class SessionStorage(MessageStorage):
    def load(self, scope: Scope) -> FlashBag:
        if 'session' not in scope:
            raise KeyError('Sessions are disabled. Flash messages depend on SessionMiddleware.')

        return FlashBag(scope['session'].get(SESSION_KEY, []))

    def save(self, scope: Scope, bag: FlashBag) -> None:
        scope['session'][SESSION_KEY] = bag.all()


_storage_map: t.Dict[str, t.Type[MessageStorage]] = {
    'session': SessionStorage,
}


class FlashMessagesMiddleware:
    def __init__(self, app: ASGIApp, storage: t.Union[MessageStorage, t.Literal["session"]] = 'session') -> None:
        self.app = app
        if isinstance(storage, str):
            storage_class = _storage_map[storage]
            storage = storage_class()
        self.storage = storage

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':  # pragma: nocover
            await self.app(scope, receive, send)
            return

        bag = self.storage.load(scope)

        async def send_wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                self.storage.save(scope, bag)
            await send(message)

        scope[SCOPE_KEY] = bag
        await self.app(scope, receive, send_wrapper)


def flash(request: Request) -> FlashBag:
    assert SCOPE_KEY in request.scope, 'Flash messages require FlashMessagesMiddleware.'
    return request.scope[SCOPE_KEY]
