import typing
from babel.core import Locale
from functools import lru_cache
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kupala.http.requests import Request
from kupala.i18n import set_locale
from kupala.i18n.protocols import HasPreferredLanguage


def _get_language_from_query(request: Request, query_param: str) -> str | None:
    return request.query_params.get(query_param)


def _get_language_from_user(request: Request) -> str | None:
    if 'auth' in request.scope and hasattr(request.user, "get_preferred_language"):
        language_provider = typing.cast(HasPreferredLanguage, request.user)
        return language_provider.get_preferred_language()
    return None


def _get_language_from_cookie(request: Request, cookie_name: str) -> str | None:
    return request.cookies.get(cookie_name)


@lru_cache(maxsize=1000)
def _get_languages_from_header(header: str) -> list[tuple[str, float]]:
    parts = header.split(",")
    result = []
    for part in parts:
        if ";" in part:
            locale, priority_ = part.split(";")
            priority = float(priority_[2:])
        else:
            locale = part
            priority = 1.0
        result.append((locale, priority))
    return sorted(result, key=lambda x: x[1], reverse=True)


def _get_language_from_header(request: Request, supported: set[str]) -> str | None:
    header = request.headers.get("accept-language", "").lower()
    for lang, _ in _get_languages_from_header(header):
        lang = lang.lower().replace('-', '_')
        if lang == "*":
            break

        if lang in supported:
            return lang
    return None


class LocaleMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        languages: list[str] | None = None,
        default_locale: str = 'en_US',
        query_param_name: str = "lang",
        cookie_name: str = "language",
        path_param: str = "_locale",
        locale_detector: typing.Callable[[Request], Locale | None] = None,
    ) -> None:
        self.app = app
        self.languages = {x.lower().replace('-', '_') for x in (languages or ["en"])}
        self.default_locale = default_locale
        self.query_param_name = query_param_name
        self.cookie_name = cookie_name
        self.path_param = path_param
        self.locale_detector = locale_detector or self.detect_locale

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                message['headers'].append(tuple([b'content-language', scope['language'].encode()]))
            await send(message)

        locale = self.locale_detector(Request(scope, receive, send))
        if not locale:
            locale = Locale.parse(self.default_locale)
        set_locale(locale)
        scope["locale"] = locale
        scope['language'] = locale.language
        scope['i18n.cookie_name'] = self.cookie_name
        await self.app(scope, receive, send_wrapper)

    def detect_locale(self, request: Request) -> Locale:
        lang = self.default_locale
        if detected_lang := _get_language_from_query(request, self.query_param_name):
            lang = detected_lang
        elif detected_lang := _get_language_from_user(request):
            lang = detected_lang
        elif detected_lang := _get_language_from_cookie(request, self.cookie_name):
            lang = detected_lang
        elif detected_lang := _get_language_from_header(request, self.languages):
            lang = detected_lang

        variant = self.find_variant(lang) or self.default_locale
        return Locale.parse(variant)

    def find_variant(self, locale: str) -> str | None:
        """
        Look up requested locale in supported list.

        If the locale does not exist, it will attempt to find the closest locale
        from the all supported. For example, if clients requests en_US, but we
        support only "en_GB" then en_GB to be returned. If no locales match
        request then None returned.
        """
        from_locale, _ = locale.lower().split('_') if '_' in locale else [locale, '']
        for supported in self.languages:
            if '_' in supported:
                language, _ = supported.lower().split('_')
                if language == from_locale:
                    return supported
            elif from_locale.lower() == supported.lower():
                return supported
        return None
