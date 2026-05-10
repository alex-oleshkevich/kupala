import typing

type Cookies = typing.Mapping[str, str]

type State = typing.Any
S = typing.TypeVar("S", bound=State)


class Request[S = State]: ...


class Websocket[S = State]: ...
