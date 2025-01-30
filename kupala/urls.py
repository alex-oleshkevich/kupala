import time
import typing

from starlette.datastructures import URL
from starlette.requests import Request

boot_time = time.time()


def static_url(request: Request, path: str, *, path_name: str = "static") -> URL:
    """Return URL for static file.
    If path is absolute, return it as is."""
    if path.startswith(("http://", "https://")):
        return URL(path)

    version = time.time() if request.app.debug else boot_time
    return request.url_for(path_name, path=path).include_query_params(v=version)


def media_url(request: Request, path: str, *, path_name: str = "media") -> URL:
    """Return URL for media file.
    If path is absolute, return it as is."""
    if path.startswith(("http://", "https://")):
        return URL(path)
    if path == "":
        return URL("")
    return request.url_for(path_name, path=path)


def abs_url_for(request: Request, name: str, **path_params: typing.Any) -> URL:
    """Return absolute URL for route."""
    return request.url_for(name, **path_params)


def url_matches(request: Request, url: URL | str) -> bool:
    """Return True if request URL matches URL."""
    value = URL(str(url))
    return request.url.path.removesuffix("/") == value.path.removesuffix("/")


def pathname_matches(request: Request, pathname: str, *, path_params: dict[str, typing.Any] | None = None) -> bool:
    url = request.url_for(pathname, **(path_params or {}))
    return url_matches(request, url)


def safe_referer(request: Request, url: str | URL) -> URL:
    redirect_url = str(url)
    hostname = request.url.hostname or "localhost"
    if redirect_url.startswith(("http://", "https://")) and not redirect_url.startswith(
        ("http://" + hostname, "https://" + hostname)
    ):
        return URL("/")
    return URL(redirect_url)


def resolve_defered_redirect_url(request: Request, fallback: URL) -> URL:
    if redirect_url := request.session.pop("__redirect_url__", None):
        return safe_referer(request, redirect_url)
    if request.query_params.get("next"):
        return safe_referer(request, request.query_params["next"])
    return fallback


def defer_redirect(request: Request, url: str | URL) -> None:
    request.session["__redirect_url__"] = str(url)
