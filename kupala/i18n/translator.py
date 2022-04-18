import os
import typing
from babel.support import LazyProxy, NullTranslations, Translations

from kupala.i18n.locale import get_locale


class Translator:
    def __init__(self, directories: list[str | os.PathLike]) -> None:
        self.directories = directories
        self._cache: dict[str, Translations] = {}

        self.load_from_directories(directories)

    def load_from_directories(self, directories: list[str | os.PathLike], domain: str = 'messages') -> None:
        for directory in directories:
            self.load_from_directory(directory, domain)

    def load_from_directory(self, directory: str | os.PathLike, domain: str = 'messages') -> None:
        for lang in os.listdir(directory):
            if os.path.isfile(os.path.join(directory, lang)):
                continue

            translations = Translations.load(str(directory), [lang], domain)
            if lang in self._cache:
                self._cache[lang].merge(translations)
            else:
                self._cache[lang] = translations

    def get_translations(self, locale: str = None) -> typing.Union[Translations, NullTranslations]:
        if locale is None:
            locale = str(get_locale())
        if locale in self._cache:
            return self._cache[locale]

        lang = locale
        if '_' in locale:
            lang, _ = locale.split('_')
        if lang in self._cache:
            return self._cache[lang]
        return NullTranslations()

    def gettext(self, msg: str, **variables: typing.Any) -> str:
        locale = variables.pop('locale', None)
        translated = self.get_translations(locale=locale).gettext(msg)
        return translated % variables if variables else translated

    def ngettext(self, /, singular: str, plural: str, count: int, **variables: typing.Any) -> str:
        variables.setdefault('count', count)
        locale = variables.pop('locale', None)
        translated = self.get_translations(locale=locale).ngettext(singular, plural, count)
        return translated % variables if variables else translated


def _lookup_callback(singular: str, plural: str = None, count: int = None, **kwargs: typing.Any) -> str:
    from kupala.application import get_current_application

    locale = kwargs.pop('locale', str(get_locale()))
    translator = get_current_application().state.translator
    if plural:
        return translator.ngettext(singular, plural, count, locale=locale, **kwargs)
    return translator.gettext(singular, locale=locale, **kwargs)


def _proxy_factory(callback: typing.Callable) -> typing.Callable:
    def lazy_gettext(singular: str, plural: str = None, count: int = None, **variables: typing.Any) -> LazyProxy:
        return LazyProxy(callback, singular, plural=plural, count=count, enable_cache=False, **variables)

    return lazy_gettext


gettext_lazy = _proxy_factory(_lookup_callback)
