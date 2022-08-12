import pathlib

from kupala.i18n import switch_locale
from kupala.i18n.translator import Translator

LOCALE_DIR = pathlib.Path(__file__).parent / "locales"


def test_translates_singular() -> None:
    translator = Translator(directories=[LOCALE_DIR])
    assert translator.gettext("Hello", locale="be") == "Вітаем"


def test_translates_singular_using_detected_locale() -> None:
    translator = Translator(directories=[LOCALE_DIR])
    with switch_locale("pl"):
        assert translator.gettext("Hello") == "Witamy"


def test_translates_singular_argument_precedence() -> None:
    translator = Translator(directories=[LOCALE_DIR])
    with switch_locale("pl"):
        assert translator.gettext("Hello", locale="be") == "Вітаем"


def test_translates_plural() -> None:
    translator = Translator(directories=[LOCALE_DIR])
    assert translator.ngettext("%(count)s apple", "%(count)s apples", 1, locale="be") == "1 яблык"
    assert translator.ngettext("%(count)s apple", "%(count)s apples", 2, locale="be") == "2 яблыкі"
    assert translator.ngettext("%(count)s apple", "%(count)s apples", 5, locale="be") == "5 яблыкаў"


def test_translates_plural_using_detected_locale() -> None:
    translator = Translator(directories=[LOCALE_DIR])
    with switch_locale("pl"):
        assert translator.ngettext("%(count)s apple", "%(count)s apples", 1) == "1 jabłko"
        assert translator.ngettext("%(count)s apple", "%(count)s apples", 2) == "2 jabłka"
        assert translator.ngettext("%(count)s apple", "%(count)s apples", 5) == "5 jablek"


def test_translates_plural_argument_precedence() -> None:
    translator = Translator(directories=[LOCALE_DIR])
    with switch_locale("pl"):
        assert translator.ngettext("%(count)s apple", "%(count)s apples", 1, locale="be") == "1 яблык"
        assert translator.ngettext("%(count)s apple", "%(count)s apples", 2, locale="be") == "2 яблыкі"
        assert translator.ngettext("%(count)s apple", "%(count)s apples", 5, locale="be") == "5 яблыкаў"
