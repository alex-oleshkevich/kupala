import asyncio
import os
import pathlib
import typing as t
from json import JSONEncoder

from kupala.http import Response, responses, route
from kupala.http.requests import Request
from tests.conftest import TestClientFactory


def test_file_response_attachment(tmpdir: os.PathLike, test_client_factory: TestClientFactory) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    @route("/")
    def view(request: Request) -> Response:
        return responses.send_file(file_path, file_name="file.bin")

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.content == b"content"
    assert res.headers["content-disposition"] == 'attachment; filename="file.bin"'


def test_file_response_inline(tmpdir: os.PathLike, test_client_factory: TestClientFactory) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    @route("/")
    def view(request: Request) -> Response:
        return responses.send_file(file_path, file_name="file.bin", inline=True)

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.content == b"content"
    assert res.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_file_response_accept_pathlike(tmpdir: os.PathLike, test_client_factory: TestClientFactory) -> None:
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    @route("/")
    def view(request: Request) -> Response:
        return responses.send_file(pathlib.Path(file_path), file_name="file.bin", inline=True)

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.content == b"content"
    assert res.headers["content-type"] == "application/octet-stream"
    assert res.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_html_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.html("<b>html text</b>")

    client = test_client_factory(routes=[view])
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


def test_json_response_with_custom_encoder_class(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.json(
            {
                "object": CustomObject(),
            },
            encoder_class=_JsonEncoder,
        )

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.json() == {"object": "<custom>"}


def test_json_response_with_custom_default(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.json(
            {
                "object": CustomObject(),
            },
            default=_default,
        )

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.json() == {"object": "<custom>"}


def test_json_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.json(
            {"user": "root"},
        )

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.json() == {"user": "root"}


def test_json_response_indentation(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.json({"user": {"details": {"name": "root"}}}, indent=4).status(201)

    client = test_client_factory(routes=[view])
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


def test_json_error_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.json_error(message="Error", errors={"field": ["error1", "error2"]}, error_code="errcode")

    client = test_client_factory(routes=[view])
    assert client.get("/").json() == {
        "message": "Error",
        "errors": {"field": ["error1", "error2"]},
        "code": "errcode",
    }


def test_redirect_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.redirect("/about")

    client = test_client_factory(routes=[view])
    res = client.get("/", allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/about"


def test_redirect_response_to_route_name(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.redirect(path_name="about")

    @route("/about", name="about")
    def about_view(request: Request) -> Response:
        return responses.json({})

    client = test_client_factory(routes=[view, about_view])
    res = client.get("/", allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/about"


def test_streaming_response_with_async_gen(test_client_factory: TestClientFactory) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    @route("/")
    def view(request: Request) -> Response:
        return responses.stream(numbers())

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.text == "1234"


def test_streaming_response_with_sync_gen(test_client_factory: TestClientFactory) -> None:
    def numbers() -> t.Generator[str, None, None]:
        for x in range(1, 5):
            yield str(x)

    @route("/")
    def view(request: Request) -> Response:
        return responses.stream(numbers())

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.text == "1234"


def test_streaming_response_with_filename(test_client_factory: TestClientFactory) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    @route("/")
    def view(request: Request) -> Response:
        return responses.stream(numbers(), content_type="text/plain", file_name="numbers.txt")

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.text == "1234"
    assert res.headers["content-disposition"] == 'attachment; filename="numbers.txt"'


def test_streaming_response_inline_disposition(test_client_factory: TestClientFactory) -> None:
    async def numbers() -> t.AsyncGenerator[str, None]:
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    @route("/")
    def view(request: Request) -> Response:
        return responses.stream(numbers(), content_type="text/plain", file_name="numbers.txt", inline=True)

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.text == "1234"
    assert res.headers["content-disposition"] == 'inline; filename="numbers.txt"'


def test_plain_text_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.text("plain text response")

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.headers["content-type"] == "text/plain; charset=utf-8"
    assert res.text == "plain text response"


def test_redirect_back_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.back()

    client = test_client_factory(routes=[view])
    res = client.get("/", headers={"referer": "http://testserver/somepage"}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "http://testserver/somepage"


def test_redirect_back_response_checks_origin(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.back()

    client = test_client_factory(routes=[view])
    res = client.get("/", headers={"referer": "http://example.com/"}, allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/"


def test_empty_response(test_client_factory: TestClientFactory) -> None:
    @route("/")
    def view(request: Request) -> Response:
        return responses.empty()

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.status_code == 204


def test_template_response(test_client_factory: TestClientFactory, tmp_path: os.PathLike) -> None:
    with open(os.path.join(tmp_path, "template_response.html"), "w") as f:
        f.write("hello {{ world }}")

    @route("/")
    def view(request: Request) -> Response:
        return responses.template("template_response.html", {"world": "world"})

    client = test_client_factory(routes=[view])
    res = client.get("/")
    assert res.text == "hello world"
