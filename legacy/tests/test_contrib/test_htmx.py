import pytest
from starlette.requests import Request
from starlette.background import BackgroundTask
from starlette.datastructures import URL
from starlette.responses import Response

from kupala.contrib import htmx


def test_is_htmx_request() -> None:
    request = Request({"type": "http", "headers": [(b"hx-request", b"yes")]})
    htmx.is_htmx_request(request)

    request = Request({"type": "http", "headers": []})
    assert not htmx.is_htmx_request(request)


def test_matches_target() -> None:
    request = Request({"type": "http", "headers": [(b"hx-target", b"main")]})
    htmx.matches_target(request, "main")
    assert not htmx.matches_target(request, "missing")


@pytest.mark.parametrize("url", ("/admin", URL("/admin")))
def test_push_url(url: str | URL) -> None:
    response = Response()
    htmx.push_url(response, url)
    assert response.headers["hx-push-url"] == "/admin"


@pytest.mark.parametrize("url", ("/admin", URL("/admin")))
def test_redirect(url: str | URL) -> None:
    response = Response()
    htmx.redirect(response, url)
    assert response.headers["hx-redirect"] == "/admin"


@pytest.mark.parametrize("url", ("/admin", URL("/admin")))
def test_location(url: str | URL) -> None:
    response = Response()
    htmx.location(response, url)
    assert response.headers["hx-location"] == "/admin"

    htmx.location(response, url, options={"target": "#main"})
    assert response.headers["hx-location"] == '{"target": "#main", "path": "/admin"}'


def test_reselect() -> None:
    response = Response()
    htmx.reselect(response, "#new")
    assert response.headers["hx-reselect"] == "#new"


def test_reswap() -> None:
    response = Response()
    htmx.reswap(response, "innerHTML")
    assert response.headers["hx-reswap"] == "innerHTML"


def test_retarget() -> None:
    response = Response()
    htmx.retarget(response, "#new")
    assert response.headers["hx-retarget"] == "#new"


def test_trigger_without_params() -> None:
    response = Response()
    htmx.trigger(response, "event")
    assert response.headers["hx-trigger"] == '{"event": {}}'


def test_trigger_with_params() -> None:
    response = Response()
    htmx.trigger(response, "event", {"a": 1})
    assert response.headers["hx-trigger"] == '{"event": {"a": 1}}'


def test_trigger_multiple_events() -> None:
    response = Response()
    htmx.trigger(response, "event")
    htmx.trigger(response, "event2", {"a": 1})
    assert response.headers["hx-trigger"] == '{"event": {}, "event2": {"a": 1}}'


def test_trigger_with_stage() -> None:
    response = Response()
    htmx.trigger(response, "event", stage="after-settle")
    assert response.headers["hx-trigger-after-settle"] == '{"event": {}}'


def test_close_modal() -> None:
    response = Response()
    htmx.close_modal(response)
    assert response.headers["hx-trigger"] == '{"modals-close": {}}'


def test_refresh() -> None:
    response = Response()
    htmx.refresh(response)
    assert response.headers["hx-trigger"] == '{"refresh": {}}'


def test_toast() -> None:
    response = Response()
    htmx.toast(response, "Message.", "success")
    assert response.headers["hx-trigger"] == '{"toast": {"message": "Message.", "category": "success"}}'


def test_toast_with_stage() -> None:
    response = Response()
    htmx.toast(response, "Message.", "success", stage="after-settle")
    assert response.headers["hx-trigger-after-settle"] == '{"toast": {"message": "Message.", "category": "success"}}'


def test_response() -> None:
    response = htmx.response(
        200,
        headers={"Content-Type": "application/json"},
        media_type="text/plain",
        background=BackgroundTask(print),
    )
    assert isinstance(response, htmx.HXResponse)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.media_type == "text/plain"
    assert response.background is not None


def test_response_class_toast() -> None:
    response = htmx.HXResponse()
    response = response.toast("Message.", "success")
    assert response.headers["hx-trigger"] == '{"toast": {"message": "Message.", "category": "success"}}'


def test_response_class_toast_with_stage() -> None:
    response = htmx.HXResponse()
    response = response.toast("Message.", "success", stage="after-settle")
    assert response.headers["hx-trigger-after-settle"] == '{"toast": {"message": "Message.", "category": "success"}}'


def test_response_class_close_modal() -> None:
    response = htmx.HXResponse()
    response = response.close_modal()
    assert response.headers["hx-trigger"] == '{"modals-close": {}}'


def test_response_class_refresh() -> None:
    response = htmx.HXResponse()
    response = response.refresh()
    assert response.headers["hx-trigger"] == '{"refresh": {}}'


@pytest.mark.parametrize("url", ("/admin", URL("/admin")))
def test_response_class_push_url(url: str | URL) -> None:
    response = htmx.HXResponse()
    response = response.push_url(url)
    assert response.headers["hx-push-url"] == "/admin"


@pytest.mark.parametrize("url", ("/admin", URL("/admin")))
def test_response_class_redirect(url: str | URL) -> None:
    response = htmx.HXResponse()
    response = response.redirect(url)
    assert response.headers["hx-redirect"] == "/admin"


@pytest.mark.parametrize("url", ("/admin", URL("/admin")))
def test_response_class_location(url: str | URL) -> None:
    response = htmx.HXResponse()
    response = response.location(url)
    assert response.headers["hx-location"] == "/admin"

    htmx.location(response, url, options={"target": "#main"})
    assert response.headers["hx-location"] == '{"target": "#main", "path": "/admin"}'


def test_response_class_reselect() -> None:
    response = htmx.HXResponse()
    response = response.reselect("#new")
    assert response.headers["hx-reselect"] == "#new"


def test_response_class_reswap() -> None:
    response = htmx.HXResponse()
    response = response.reswap("innerHTML")
    assert response.headers["hx-reswap"] == "innerHTML"


def test_response_class_retarget() -> None:
    response = htmx.HXResponse()
    response = response.retarget("#new")
    assert response.headers["hx-retarget"] == "#new"


def test_response_class_trigger_without_params() -> None:
    response = htmx.HXResponse()
    response = response.trigger("event")
    assert response.headers["hx-trigger"] == '{"event": {}}'


def test_response_class_trigger_with_params() -> None:
    response = htmx.HXResponse()
    response = response.trigger("event", {"a": 1})
    assert response.headers["hx-trigger"] == '{"event": {"a": 1}}'


def test_response_class_trigger_multiple_events() -> None:
    response = htmx.HXResponse()
    response = response.trigger("event")
    response = response.trigger("event2", {"a": 1})
    assert response.headers["hx-trigger"] == '{"event": {}, "event2": {"a": 1}}'


def test_response_class_trigger_with_stage() -> None:
    response = htmx.HXResponse()
    response = response.trigger("event", stage="after-settle")
    assert response.headers["hx-trigger-after-settle"] == '{"event": {}}'
