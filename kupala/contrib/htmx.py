import json
import typing

from starlette.background import BackgroundTask
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import Response

R = typing.TypeVar("R", bound=Response)
ToastCategory = typing.Literal["error", "success"]
TriggerStage = typing.Literal["immediate", "after-swap", "after-settle"]
SwapTarget = typing.Literal[
    "innerHTML", "outerHTML", "beforebegin", "afterbegin", "beforeend", "afterend", "delete", "none"
]


def is_htmx_request(request: Request) -> bool:
    return "hx-request" in request.headers


def matches_target(request: Request, target: str) -> bool:
    return request.headers.get("hx-target", "") == target


def push_url(response: R, url: str | URL) -> R:
    response.headers["hx-push-url"] = str(url)
    return response


def redirect(response: R, url: str | URL) -> R:
    response.headers["hx-redirect"] = str(url)
    return response


class LocationOptions(typing.TypedDict):
    path: typing.NotRequired[str]

    target: typing.NotRequired[str]
    """The target to swap the response into."""

    swap: typing.NotRequired[SwapTarget]
    """How the response will be swapped in relative to the target."""

    select: typing.NotRequired[str]
    """Allows you to select the content you want swapped from a response."""


def location(response: R, url: str | URL, options: LocationOptions | None = None) -> R:
    params = str(url)
    if options is not None:
        options["path"] = str(url)
        params = json.dumps(options)
    response.headers["hx-location"] = params
    return response


def reselect(response: R, selector: str) -> R:
    response.headers["hx-reselect"] = selector
    return response


def reswap(response: R, target: SwapTarget) -> R:
    response.headers["hx-reswap"] = target
    return response


def retarget(response: R, target: str) -> R:
    response.headers["hx-retarget"] = target
    return response


def trigger(response: R, event: str, data: typing.Any = None, *, stage: TriggerStage = "immediate") -> R:
    hx_event = {
        "immediate": "hx-trigger",
        "after-swap": "hx-trigger-after-swap",
        "after-settle": "hx-trigger-after-settle",
    }.get(stage, "hx-trigger")

    triggers = json.loads(response.headers.get(hx_event, "{}"))
    triggers[event] = data or {}
    response.headers[hx_event] = json.dumps(triggers)
    return response


def close_modal(response: R) -> R:
    return trigger(response, "modals-close")


def refresh(response: R) -> R:
    """Refresh table items."""
    return trigger(response, "refresh")


def toast(response: R, message: str, category: ToastCategory = "success", *, stage: TriggerStage = "immediate") -> R:
    return trigger(response, "toast", {"message": message, "category": category}, stage=stage)


class HXResponse(Response):
    def toast(
        self,
        message: str,
        category: ToastCategory = "success",
        stage: TriggerStage = "immediate",
    ) -> typing.Self:
        return toast(self, str(message), category, stage=stage)

    def success_toast(self, message: str) -> typing.Self:
        return self.toast(message, "success")

    def error_toast(self, message: str) -> typing.Self:
        return self.toast(message, "error")

    def close_modal(self) -> typing.Self:
        return close_modal(self)

    def refresh(self) -> typing.Self:
        return refresh(self)

    def redirect(self, url: str | URL) -> typing.Self:
        return redirect(self, url)

    def push_url(self, url: str | URL) -> typing.Self:
        return push_url(self, url)

    def location(self, url: str | URL, options: LocationOptions | None = None) -> typing.Self:
        return location(self, url, options)

    def reselect(self, selector: str) -> typing.Self:
        return reselect(self, selector)

    def retarget(self, selector: str) -> typing.Self:
        return retarget(self, selector)

    def reswap(self, target: SwapTarget) -> typing.Self:
        return reswap(self, target)

    def trigger(self, event: str, data: typing.Any = None, stage: TriggerStage = "immediate") -> typing.Self:
        return trigger(self, event, data, stage=stage)


def response(
    status_code: int = 204,
    headers: typing.Mapping[str, str] | None = None,
    media_type: str | None = None,
    background: BackgroundTask | None = None,
) -> HXResponse:
    return HXResponse(
        status_code=status_code,
        headers=headers,
        media_type=media_type,
        background=background,
    )
