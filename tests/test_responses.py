import asyncio
import os
import pathlib
import typing as t

from starlette.testclient import TestClient

from kupala.contracts import TemplateRenderer
from kupala.json import JSONEncoder
from kupala.requests import Request
from kupala.responses import response
from kupala.sessions import InMemoryBackend, SessionMiddleware


def test_sends_file(tmpdir, app):
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    def view(request: Request):
        return response(request).send_file(file_path, file_name="file.bin")

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.content == b"content"
    assert (
        http_response.headers["content-disposition"]
        == 'attachment; filename="file.bin"'
    )


def test_sends_inline(tmpdir, app):
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    def view(request: Request):
        return response(request).send_file(file_path, file_name="file.bin", inline=True)

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.content == b"content"
    assert http_response.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_accepts_path_class(tmpdir, app):
    file_path = os.path.join(tmpdir, "file.bin")
    with open(str(file_path), "wb") as f:
        f.write(b"content")

    def view(request: Request):
        return response(request).send_file(
            pathlib.Path(file_path), file_name="file.bin", inline=True
        )

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.content == b"content"
    assert http_response.headers["content-type"] == "application/octet-stream"
    assert http_response.headers["content-disposition"] == 'inline; filename="file.bin"'


def test_html(app):
    def view(request: Request):
        return response(request).html("<b>html text</b>")

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.headers["content-type"] == "text/html; charset=utf-8"
    assert http_response.text == "<b>html text</b>"


class CustomObject:
    pass


def _default(o):
    if isinstance(o, CustomObject):
        return "<custom>"
    return o


class _JsonEncoder(JSONEncoder):
    def default(self, o):
        return _default(o)


def test_custom_encoder_class(app):
    def view(request: Request):
        return response(request).json(
            {
                "object": CustomObject(),
            },
            encoder_class=_JsonEncoder,
        )

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.json() == {"object": "<custom>"}


def test_custom_default(app):
    def view(request: Request):
        return response(request).json(
            {
                "object": CustomObject(),
            },
            default=_default,
        )

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.json() == {"object": "<custom>"}


def test_json(app):
    def view(request: Request):
        return response(request, 201).json({"user": "root"})

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.status_code == 201
    assert http_response.json() == {"user": "root"}


def test_json_indents(app):
    def view(request: Request):
        return response(request, 201).json(
            {"user": {"details": {"name": "root"}}}, indent=4
        )

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.status_code == 201
    assert http_response.text == (
        "{\n"
        '    "user": {\n'
        '        "details": {\n'
        '            "name": "root"\n'
        "        }\n"
        "    }\n"
        "}"
    )


def test_redirect(app):
    def view(request: Request):
        return response(request).redirect("/about")

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/", allow_redirects=False)
    assert http_response.status_code == 302
    assert http_response.headers["location"] == "/about"


def test_redirect_to_route_name(app):
    def view(request: Request):
        return response(request).redirect("profile")

    app.routes.get("/", view)
    app.routes.get("/profile", view, name="profile")

    client = TestClient(app)
    http_response = client.get("/", allow_redirects=False)
    assert http_response.status_code == 302
    assert http_response.headers["location"] == "/profile"


def test_streaming_response_with_async_gen(app):
    async def numbers():
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request):
        return response(request).stream(numbers())

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.text == "1234"


def test_streaming_response_with_sync_gen(app):
    def numbers():
        for x in range(1, 5):
            yield str(x)

    def view(request: Request):
        return response(request).stream(numbers())

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.text == "1234"


def test_streaming_response_with_filename(app):
    async def numbers():
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request):
        return response(request).stream(
            numbers(), media_type="text/plain", file_name="numbers.txt"
        )

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.text == "1234"
    assert http_response.headers["content-disposition"] == (
        'attachment; filename="numbers.txt"'
    )


def test_disposition_inline(app):
    async def numbers():
        for x in range(1, 5):
            yield str(x)
            await asyncio.sleep(0)

    def view(request: Request):
        return response(request).stream(
            numbers(), media_type="text/plain", file_name="numbers.txt", inline=True
        )

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.text == "1234"
    assert http_response.headers["content-disposition"] == (
        'inline; filename="numbers.txt"'
    )


class _FormatRenderer(TemplateRenderer):
    def render(
        self,
        template_name: str,
        context: dict[str, t.Any] = None,
        request: Request = None,
    ) -> str:
        with open(template_name, "r") as f:
            return f.read() % context


def test_template_response(tmpdir, app):
    template_path = os.path.join(tmpdir, "index.html")
    with open(template_path, "w") as f:
        f.write("Username: %(username)s")

    def view(request: Request):
        return response(request).template(template_path, {"username": "root"})

    app.routes.get("/", view)
    app.bind(TemplateRenderer, _FormatRenderer())

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.text == "Username: root"


def test_render(tmpdir, app):
    template_path = os.path.join(tmpdir, "index.html")
    with open(template_path, "w") as f:
        f.write("Username: %(username)s")

    def view(request: Request):
        return response(request).template(template_path, {"username": "root"})

    app.bind(TemplateRenderer, _FormatRenderer())
    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.text == "Username: root"


def test_plain_text(app):
    def view(request: Request):
        return response(request).text("plain text response")

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get("/")
    assert http_response.headers["content-type"] == "text/plain; charset=utf-8"
    assert http_response.text == "plain text response"


def test_back_response(app):
    backend = InMemoryBackend()
    app.middleware.use(SessionMiddleware, secret_key="key", backend=backend)

    def view(request: Request):
        return response(request).back({"user": "root"})

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get(
        "/", headers={"referer": "https://testserver/profile"}, allow_redirects=False
    )
    session_id = http_response.cookies["session"]
    assert http_response.headers["location"] == "https://testserver/profile"
    assert backend.data == {session_id: {"_redirect_data": {"user": "root"}}}


def test_back_response_redirects_to_homepage_if_origin_invalid(app):
    backend = InMemoryBackend()
    app.middleware.use(SessionMiddleware, secret_key="key", backend=backend)

    def view(request: Request):
        return response(request).back()

    app.routes.get("/", view)

    client = TestClient(app)
    http_response = client.get(
        "/", headers={"referer": "example.com/profile"}, allow_redirects=False
    )
    assert http_response.headers["location"] == "/"
