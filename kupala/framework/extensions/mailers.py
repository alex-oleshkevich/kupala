import mailers

from kupala.application import App
from kupala.extensions import Extension
from kupala.mailers import MailComposer


class MailExtension(Extension):
    def __init__(
        self,
        mailers: dict[str, str],
        from_address: str,
        default_mailer: str = "default",
    ) -> None:
        self.mailers = mailers
        self.from_address = from_address
        self.default = default_mailer

    def register(self, app: App) -> None:
        mailers.configure(self.mailers)
        for name, url in self.mailers.items():
            app.singleton(f"mailers.{name}", lambda: mailers.registry.get(name))

        app.alias(f"mailers.{self.default}", mailers.Mailer)
        app.singleton(MailComposer, MailComposer, aliases="mail_composer")
        app.config.update(
            {
                "mailers": {
                    "from_address": self.from_address,
                }
            }
        )
