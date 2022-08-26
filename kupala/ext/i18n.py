import os
import typing
from babel.core import Locale

from kupala.application import App, Extension
from kupala.http.middleware import LocaleMiddleware
from kupala.http.middleware.timezone import TimezoneMiddleware
from kupala.http.requests import Request
from kupala.i18n import formatters
from kupala.i18n.translator import Translator


def get_translator(request: Request) -> Translator:
    """Get translator instance configured to this application."""
    return request.app.state.translator


def use_i18n(
    translation_dir: str | os.PathLike,
    default_locale: str = "en",
    locales: list[str] | None = None,
    locale_query_param: str = "lang",
    locale_cookie_name: str = "language",
    locale_path_param: str = "path_param",
    locale_detector: typing.Callable[[Request], Locale | None] = None,
) -> Extension:
    """
    Enable localization support.

    This extension sets up translator instance and adds middleware that detects current request language/locale.
    """

    def extension(app: App) -> None:
        translator = Translator(directories=[app.base_dir / translation_dir])
        app.state.translator = translator

        app.add_middleware(
            LocaleMiddleware,
            languages=locales,
            default_locale=default_locale,
            query_param_name=locale_query_param,
            cookie_name=locale_cookie_name,
            path_param=locale_path_param,
            locale_detector=locale_detector,
        )

        app.add_template_global(_=translator.gettext, __=translator.gettext, _p=translator.ngettext)
        app.add_template_filters(
            datetime=formatters.format_datetime,
            date=formatters.format_date,
            time=formatters.format_time,
            timedelta=formatters.format_timedelta,
            number=formatters.format_number,
            currency=formatters.format_currency,
            percent=formatters.format_percent,
            scientific=formatters.format_scientific,
        )
        app.add_template_extensions("jinja2.ext.i18n")
        app.get_jinja_env().install_gettext_translations(translator)  # type: ignore[attr-defined]

    return extension


def use_timezones(
    timezone: str = "UTC",
    timezone_detector: typing.Callable[[Request], str | None] = None,
) -> Extension:
    """Enable timezone support."""

    def extension(app: App) -> None:
        app.add_middleware(
            TimezoneMiddleware,
            fallback=timezone,
            timezone_detector=timezone_detector,
        )

    return extension
