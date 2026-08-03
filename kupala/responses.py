import typing

from starlette.responses import Response

from kupala.requests import Request

__all__ = ["Response", "response"]


class ResponseBuilder:
    def __init__(
        self,
        request: Request,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        cookies: typing.Mapping[str, str] | None = None,
        delete_cookies: typing.Sequence[str] = (),
    ) -> None:
        self._request = request
        self._status_code = status_code
        self._headers = headers
        self._cookies = cookies
        self._delete_cookies = delete_cookies

    def template(self, template_name: str, context: typing.Mapping[str, typing.Any] | None = None) -> Response:
        return Response()

    def json(self) -> Response:
        return Response()

    def empty(self) -> Response:
        return Response()

    def text(self) -> Response:
        return Response()

    def html(self) -> Response:
        return Response()

    def redirect(self) -> Response:
        return Response()

    def redirect_to(self) -> Response:
        return Response()

    def back(self) -> Response:
        return Response()

    def file(self) -> Response:
        return Response()

    def stream(self) -> Response:
        return Response()

    def sse(self) -> Response:
        return Response()

    def with_flash(self, message: str, category: str) -> typing.Self:
        return self

    def with_cookie(self) -> typing.Self:
        return self

    def with_header(self) -> typing.Self:
        return self

    def with_status(self) -> typing.Self:
        return self

    def with_vary(self) -> typing.Self:
        return self

    def with_cache(self) -> typing.Self:
        return self

    def with_delete_cookie(self) -> typing.Self:
        return self

    def with_signed_cookie(self) -> typing.Self:
        return self

    def with_encrypted_cookie(self) -> typing.Self:
        return self


def response(
    request: Request,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    delete_cookies: typing.Sequence[str] = (),
) -> ResponseBuilder:
    return ResponseBuilder(
        request=request,
        status_code=status_code,
        headers=headers,
        cookies=cookies,
        delete_cookies=delete_cookies,
    )
