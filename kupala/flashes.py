import dataclasses
import typing as t

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.requests import Request


class Types:
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclasses.dataclass
class FlashMessage:
    type: str
    message: str

    Types = Types

    def __str__(self) -> str:
        return self.message

    def __json__(self) -> dict:
        return dataclasses.asdict(self)


class FlashBag:
    def __init__(self, messages: t.List[FlashMessage] = None) -> None:
        self._messages: t.List[FlashMessage] = messages or []

    def error(self, message: str) -> None:
        self.add(message, Types.ERROR)

    def errors(self) -> list[FlashMessage]:
        return [m for m in self if m.type == FlashMessage.Types.ERROR]

    def success(self, message: str) -> None:
        self.add(message, Types.SUCCESS)

    def successful(self) -> list[FlashMessage]:
        return [m for m in self if m.type == FlashMessage.Types.SUCCESS]

    def info(self, message: str) -> None:
        self.add(message, Types.INFO)

    def informational(self) -> list[FlashMessage]:
        return [m for m in self if m.type == FlashMessage.Types.INFO]

    def warning(self, message: str) -> None:
        self.add(message, Types.WARNING)

    def warnings(self) -> list[FlashMessage]:
        return [m for m in self if m.type == FlashMessage.Types.WARNING]

    def add(self, message: str, type_: str = "info") -> None:
        self._messages.append(FlashMessage(type_, message))

    def add_many(self, messages: list[FlashMessage]) -> None:
        self._messages.extend(messages)

    def get(self, type_: str = None) -> t.List[FlashMessage]:
        if not type_:
            return [m for m in self._messages]

        return [m for m in self._messages if m.type == type_]

    def all(self) -> t.List[FlashMessage]:
        return self._messages

    def reader(self) -> t.Generator[FlashMessage, None, None]:
        while True:
            if not len(self._messages):
                break

            message = self._messages.pop()
            yield message

    def flush(self) -> None:
        self._messages = []

    __call__ = add

    def __iter__(self) -> t.Iterator[FlashMessage]:
        return iter(self.reader())

    def __len__(self) -> int:
        return len(self._messages)

    def __bool__(self) -> bool:
        return len(self) > 0


class FlashMessagesMiddleware:
    """Middleware to handle flash messages.

    Injects FlashBag into request scope as "flash_messages" key.

    Usage:
        scope['flash_messages'].add(message, type)
        messages = scope['flash_messages'].all()
    """

    session_key = "_flashes"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        assert "session" in scope, (
            "Flash messaging depends on SessionMiddleware. "
            "In middleware is installed make sure that it is above "
            f'"{self.__class__.__name__}" middleware.'
        )
        await scope["session"].load()
        messages = scope["session"].get(self.session_key, [])
        bag = FlashBag([FlashMessage(**message) for message in messages])
        scope["flash_messages"] = bag

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                scope["session"][self.session_key] = bag.all()
            await send(message)

        await self.app(scope, receive, send_wrapper)


def get_flash_messages(request: Request) -> FlashBag:
    return request.scope["flash_messages"]


flash = get_flash_messages
