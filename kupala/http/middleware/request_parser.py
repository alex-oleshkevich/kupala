import anyio
import re
import typing
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.http import UnsupportedMediaType
from kupala.http.exceptions import RequestTimeout
from kupala.http.request_parsers import JSONParser, MultipartParser, RequestParser, URLEncodedParser

ParserType = typing.Literal['multipart', 'urlencoded', 'json']
_KNONWN_PARSERS: dict[ParserType, typing.Type[RequestParser]] = {
    'multipart': MultipartParser,
    'urlencoded': URLEncodedParser,
    'json': JSONParser,
}


class RequestParserMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        parsers: list[ParserType | RequestParser],
        max_length: int = 8 * 1024**2,
        read_timeout: float = 30,
        passthrough: list[str | typing.Pattern] | None = None,
    ) -> None:
        self.app = app
        self._max_length = max_length
        self._read_timeout = read_timeout
        self._passthrough = passthrough or []
        self._parsers = list(self._to_parsers_list(parsers))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':  # pragma: nocover
            return await self.app(scope, receive, send)

        if scope['method'] not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return await self.app(scope, receive, send)

        connection = HTTPConnection(scope, receive)
        content_type = connection.headers.get('content-type', '')
        parser = self._find_parser(content_type)
        if parser:
            try:
                async with anyio.fail_after(self._read_timeout):
                    scope['body_params'] = await parser.parse(connection, receive)
            except TimeoutError:
                raise RequestTimeout(f'Did not complete request parsing after {self._read_timeout} seconds.')

        elif self._should_passthrough(content_type) is False:
            raise UnsupportedMediaType(f'No parser configured to parse "{content_type}" type.')
        await self.app(scope, receive, send)

    def _should_passthrough(self, content_type: str) -> bool:
        for mime_to_pass in self._passthrough:
            if re.match(mime_to_pass, content_type):
                return True
        return False

    def _to_parsers_list(
        self, parsers: list[ParserType | RequestParser]
    ) -> typing.Generator[RequestParser, None, None]:
        for parser_type in parsers:
            if isinstance(parser_type, str) and parser_type not in _KNONWN_PARSERS:
                available = ', '.join(_KNONWN_PARSERS.keys())
                raise KeyError(f'Unknown parser alias: {parser_type}. Choose from: {available}.')

            if parser_class := _KNONWN_PARSERS.get(parser_type):  # type: ignore[arg-type]
                yield parser_class(max_length=self._max_length)
            else:
                yield typing.cast(RequestParser, parser_type)

    def _find_parser(self, content_type: str) -> RequestParser | None:
        for parser in self._parsers:
            if parser.supports(content_type):
                return parser
        return None
