import pathlib

from kupala.application import App, set_current_application
from kupala.http import Routes
from kupala.i18n import switch_locale
from kupala.i18n.translator import Translator
from kupala.i18n.utils import _, gettext_lazy

LOCALE_DIR = pathlib.Path(__file__).parent / "locales"


def test_underscode_shortcut_translates() -> None:
    translator = Translator(directories=[LOCALE_DIR])
    app = App(secret_key="key", routes=Routes())
    app.state.translator = translator
    set_current_application(app)

    with switch_locale("pl"):
        assert str(_("Hello")) == "Witamy"
        assert str(gettext_lazy("Hello")) == "Witamy"