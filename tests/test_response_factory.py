import asyncio
import os
import pathlib
import typing as t
from json import JSONEncoder

from kupala.contracts import TemplateRenderer
from kupala.http import Routes
from kupala.http.requests import Request
from kupala.http.response_factories import response
from kupala.http.responses import Response
from tests.conftest import TestClientFactory


def test_sends_file(tmpdir: os.PathLike, test_client_factory: TestClientFactory, routes: Routes) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    def view(request: Request) -> Response:
        return response(request).send_file(file_path, file_name="file.bin")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.content == b"content"
    assert res.headers["content-disposition"] == 'attachment; filename="file.bin"'


def test_sends_inline(tmpdir: os.PathLike, test_client_factory: TestClientFactory, routes: Routes) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    def view(request: Request) -> Response:
        return response(request).send_file(file_path, file_name="file.bin", inline=True)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.content == b"content"
    assert res.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_accepts_path_class(tmpdir: os.PathLike, test_client_factory: TestClientFactory, routes: Routes) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    def view(request: Request) -> Response:
        return response(request).send_file(pathlib.Path(file_path), file_name="file.bin", inline=True)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.content == b"content"
    assert res.headers["content-type"] == "application/octet-stream"
    assert res.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_html(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).html("<b>html text</b>")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.headers["content-type"] == "text/html; charset=utf-8"
    assert res.text == "<b>html text</b>"


class CustomObject:
    pass


def _default(o: t.Any) -> t.Any:
    if isinstance(o, CustomObject):
        return "<custom>"
    return o


class _JsonEncoder(JSONEncoder):
    def default(self, o: t.Any) -> t.Any:
        return _default(o)


def test_custom_encoder_class(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).json(
            {
                "object": CustomObject(),
            },
            encoder_class=_JsonEncoder,
        )

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.json() == {"object": "<custom>"}


def test_custom_default(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).json(
            {
                "object": CustomObject(),
            },
            default=_default,
        )

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.json() == {"object": "<custom>"}


def test_json(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).json(
            {"user": "root"},
        )

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.json() == {"user": "root"}


def test_json_indents(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request, 201).json({"user": {"details": {"name": "root"}}}, indent=4)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.status_code == 201
    assert (
        res.text
        == """{
    "user":{
        "details":{
            "name":"root"
        }
    }
}"""
    )


def test_json_error(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).json_error(message="Error", errors={"field": ["error1", "error2"]}, code="errcode")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    assert client.get("/").json() == {
        "message": "Error",
        "errors": {"field": ["error1", "error2"]},
        "code": "errcode",
    }


def test_redirect(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).redirect("/about")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/", allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/about"


def test_redirect_to_route_name(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).redirect(path_name="about")

    routes.add("/", view)
    routes.add("/about", view, name="about")
    client = test_client_factory(routes=routes)
    res = client.get("/", allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/about"


def test_streaming_response_with_async_gen(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> Response:
        return response(request).stream(numbers())

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.text == "1234"


def test_streaming_response_with_sync_gen(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def numbers() -> t.Generator[str, None, None]:
        for x in range(1, 5):
            yield str(x)

    def view(request: Request) -> Response:
        return response(request).stream(numbers())

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.text == "1234"


def test_with_filename(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> Response:
        return response(request).stream(numbers(), content_type="text/plain", file_name="numbers.txt")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.text == "1234"
    assert res.headers["content-disposition"] == 'attachment; filename="numbers.txt"'


def test_disposition_inline(test_client_factory: TestClientFactory, routes: Routes) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request) -> Response:
        return response(request).stream(numbers(), content_type="text/plain", file_name="numbers.txt", inline=True)

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.text == "1234"
    assert res.headers["content-disposition"] == 'inline; filename="numbers.txt"'


def test_plain_text(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).text("plain text response")

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.headers["content-type"] == "text/plain; charset=utf-8"
    assert res.text == "plain text response"


def test_redirect_back(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).back()

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/", headers={"referer": "http://testserver/somepage"}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "http://testserver/somepage"


def test_redirect_back_checks_origin(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).back()

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/", headers={"referer": "http://example.com/"}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/"


def test_empty(test_client_factory: TestClientFactory, routes: Routes) -> None:
    def view(request: Request) -> Response:
        return response(request).empty()

    routes.add("/", view)
    client = test_client_factory(routes=routes)
    res = client.get("/")
    assert res.status_code == 204


def test_template(test_client_factory: TestClientFactory, routes: Routes, format_renderer: TemplateRenderer) -> None:
    def view(request: Request) -> Response:
        return response(request).template("hello world")

    routes.add("/", view)
    client = test_client_factory(routes=routes, renderer=format_renderer)
    res = client.get("/")
    assert res.text == "hello world"
