import pytest

from kupala.authentication import AuthState
from kupala.requests import QueryParams, Request
from kupala.sessions import InMemoryBackend, Session


@pytest.fixture()
def form_request():
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "client": ("0.0.0.0", "8080"),
        "headers": [
            [b"accept", b"text/html"],
            [b"content-type", b"application/x-www-form-urlencoded"],
        ],
    }

    async def receive(*args):
        return {
            "type": "http.request",
            "body": b"id=1&email=root@localhost",
            "more_body": False,
        }

    return Request(scope, receive)


@pytest.fixture()
def json_request():
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            [b"content-type", b"application/json"],
            [b"accept", b"application/json"],
        ],
    }

    async def receive(*args):
        return {
            "type": "http.request",
            "body": b'{"key":"value", "key2": 2}',
            "more_body": False,
        }

    return Request(scope, receive)


@pytest.fixture()
def xhr_request():
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [
            [b"content-type", b"application/json"],
            [b"x-requested-with", b"XMLHttpRequest"],
        ],
    }

    async def receive(*args):
        return {
            "type": "http.request",
            "body": b'{"key":"value", "key2": 2}',
            "more_body": False,
        }

    return Request(scope, receive)


@pytest.fixture()
def https_request():
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "headers": [],
    }

    async def receive(*args):
        return {
            "type": "http.request",
            "body": b'{"key":"value", "key2": 2}',
            "more_body": False,
        }

    return Request(scope, receive)


def test_wants_json(json_request, form_request, xhr_request):
    assert json_request.wants_json
    assert not form_request.wants_json
    assert not xhr_request.wants_json


def test_is_post(json_request):
    assert json_request.is_post


def test_secure(form_request, https_request):
    assert https_request.secure
    assert not form_request.secure


def test_is_ajax(form_request, xhr_request):
    assert xhr_request.is_ajax
    assert not form_request.is_ajax


def test_ip(form_request):
    assert form_request.ip == "0.0.0.0"


@pytest.fixture()
def query_params():
    return QueryParams(
        "integer=1&float=3.14&string=email&"
        "ints[]=1&ints[]=2&strs[]=string&strs[]=string2&"
        "floats[]=1.1&floats[]=1.2&list[]=1&list[]=value"
    )


def test_query_params_int(query_params):
    assert query_params.get_int("integer") == 1
    assert query_params.get_int("missing", 100) == 100
    assert query_params.get_int("missing") is None


def test_query_params_ints(query_params):
    assert query_params.get_int_list("ints[]") == [1, 2]
    assert query_params.get_int_list("missing[]") == []


def test_query_params_float(query_params):
    assert query_params.get_float("float") == 3.14
    assert query_params.get_float("missing", 1.9) == 1.9
    assert query_params.get_float("missing") is None


def test_query_params_floats(query_params):
    assert query_params.get_float_list("ints[]") == [1, 2]
    assert query_params.get_float_list("missing") == []


def test_query_params_list(query_params):
    assert query_params.get_list("list[]") == ["1", "value"]
    assert query_params.get_list("missing") == []


def test_creates_query_params(form_request):
    assert form_request.query_params is not None


def test_url_matches():
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": (b"example.com", 80),
            "query_string": b"csrf-token=TOKEN",
            "path": "/account/login",
            "headers": {},
        }
    )
    assert request.url_matches(r"/account/login")
    assert request.url_matches(r".*ogin")
    assert request.url_matches(r"/account/*")
    assert not request.url_matches(r"/admin")


def test_full_url_matches():
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("example.com", 80),
            "query_string": b"csrf-token=TOKEN",
            "path": "/account/login",
            "headers": {},
        }
    )
    assert request.full_url_matches(r"http://example.com")
    assert request.full_url_matches(r"http://example.com/account/*")
    assert request.full_url_matches("http://example.com/account/login")
    assert request.full_url_matches("http://example.com/account/login?csrf-token=TOKEN")
    assert not request.full_url_matches(r"http://another.com/account/login")


def test_auth(json_request):
    json_request.scope["auth"] = AuthState()
    assert isinstance(json_request.auth, AuthState)


def test_session(json_request):
    json_request.scope["session"] = Session(InMemoryBackend())
    assert isinstance(json_request.session, Session)


@pytest.mark.asyncio
async def test_old_data(json_request):
    session_id = "sid"
    json_request.scope["session"] = Session(
        InMemoryBackend({"sid": {"_redirect_data": {"user": "root"}}}), session_id
    )
    await json_request.session.load()
    assert json_request.old_data() == {"user": "root"}
