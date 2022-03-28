import abc
import typing
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.formparsers import FormParser, MultiPartParser
from starlette.requests import ClientDisconnect, HTTPConnection
from starlette.types import Receive

from kupala import json
from kupala.http import FormData, UploadFile
from kupala.http.exceptions import RequestTooLarge


class RequestParser:
    content_type: str

    def __init__(self, max_length: int) -> None:
        self.max_length = max_length

    def supports(self, content_type: str) -> bool:
        return content_type.startswith(self.content_type)

    @abc.abstractmethod
    async def parse(self, connection: HTTPConnection, receive: Receive) -> typing.Any:
        raise NotImplementedError

    async def stream(self, receive: Receive, max_size: int) -> typing.AsyncGenerator[bytes, None]:
        bytes_read = 0
        while True:
            message = await receive()
            if message['type'] == 'http.request':
                body = message.get('body', b'')
                bytes_read += len(body)
                if bytes_read > max_size:
                    raise RequestTooLarge(f'Request is too large. Read: {bytes_read}, limit {max_size}.')

                if body:
                    yield body
                if not message.get('more_body', False):
                    break
            elif message['type'] == 'http.disconnect':
                raise ClientDisconnect()
        yield b''


class URLEncodedParser(RequestParser):
    content_type = 'application/x-www-form-urlencoded'

    async def parse(self, connection: HTTPConnection, receive: Receive) -> typing.Any:
        form_parser = FormParser(connection.headers, self.stream(receive, self.max_length))
        form_data = await form_parser.parse()
        return FormData(form_data)


class MultipartParser(RequestParser):
    content_type = 'multipart/form-data'

    async def parse(self, connection: HTTPConnection, receive: Receive) -> typing.Any:
        multipart_parser = MultiPartParser(connection.headers, self.stream(receive, self.max_length))
        form_data = await multipart_parser.parse()
        return FormData(
            [
                (key, UploadFile.from_base_upload_file(file) if isinstance(file, StarletteUploadFile) else file)
                for key, file in form_data.multi_items()
            ]
        )


class JSONParser(RequestParser):
    content_type = 'application/json'

    def __init__(self, max_length: int, json_loader: typing.Callable = json.loads) -> None:
        super().__init__(max_length=max_length)
        self.json_loader = json_loader

    async def parse(self, connection: HTTPConnection, receive: Receive) -> typing.Any:
        chunks = []
        async for chunk in self.stream(receive, self.max_length):
            chunks.append(chunk)
        return self.json_loader(b''.join(chunks))
