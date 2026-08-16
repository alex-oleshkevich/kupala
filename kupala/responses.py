import typing

from starlette.responses import PlainTextResponse, Response

from kupala.requests import Request

__all__ = ["Response", "response"]


class ResponseBuilder:
    def __init__(self, request: Request) -> None:
        self._request = request
        self._cookies: dict[str, str] = {}
        self._delete_cookies: tuple[str, ...] = ()

    def clone(
        self,
        *,
        cookies: typing.Mapping[str, str] | None = None,
        delete_cookies: typing.Sequence[str] | None = None,
    ) -> typing.Self:
        clone = type(self)(self._request)
        clone._cookies = dict(self._cookies if cookies is None else cookies)
        clone._delete_cookies = tuple(self._delete_cookies if delete_cookies is None else delete_cookies)
        return clone

    def _apply_cookies(self, response: Response) -> Response:
        for key, value in self._cookies.items():
            response.set_cookie(key, value)
        for key in self._delete_cookies:
            response.delete_cookie(key)
        return response

    def template(
        self,
        template_name: str,
        context: typing.Mapping[str, typing.Any] | None = None,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def json(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def empty(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def text(
        self,
        text: str,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(PlainTextResponse(text, status_code=status_code, headers=headers))

    def html(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def redirect(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def redirect_to(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def back(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def file(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def stream(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def sse(
        self,
        *,
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
    ) -> Response:
        return self._apply_cookies(Response(status_code=status_code, headers=headers))

    def with_flash(self, message: str, category: str) -> typing.Self:
        return self.clone()

    def with_cookie(self, key: str, value: str) -> typing.Self:
        cookies = self._cookies.copy()
        cookies[key] = value
        return self.clone(cookies=cookies)

    def with_vary(self) -> typing.Self:
        return self.clone()

    def with_cache(self) -> typing.Self:
        return self.clone()

    def with_delete_cookie(self, key: str) -> typing.Self:
        return self.clone(delete_cookies=(*self._delete_cookies, key))

    def with_signed_cookie(self) -> typing.Self:
        return self.clone()

    def with_encrypted_cookie(self) -> typing.Self:
        return self.clone()


def response(request: Request) -> ResponseBuilder:
    return ResponseBuilder(request)
