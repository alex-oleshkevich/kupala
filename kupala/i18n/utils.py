import typing
from babel.support import LazyProxy

from kupala.i18n import get_locale
from kupala.i18n.translator import Translator


def _lookup_callback(singular: str, plural: str | None = None, count: int | None = None, **kwargs: typing.Any) -> str:
    from kupala.application import get_current_application

    locale = kwargs.pop("locale", str(get_locale()))
    translator = get_current_application().get(Translator)
    if plural:
        assert count, "Count must be non-None when plural=True"
        return translator.ngettext(singular, plural, count, locale=locale, **kwargs)
    return translator.gettext(singular, locale=locale, **kwargs)


def _proxy_factory(callback: typing.Callable) -> typing.Callable:
    def lazy_gettext(
        singular: str,
        plural: str | None = None,
        count: int | None = None,
        **variables: typing.Any,
    ) -> LazyProxy:
        return LazyProxy(callback, singular, plural=plural, count=count, enable_cache=False, **variables)

    return lazy_gettext


gettext_lazy = _proxy_factory(_lookup_callback)
_ = gettext_lazy
