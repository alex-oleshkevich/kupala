import typing as t

from kupala.application import App
from kupala.authentication import LoginManager
from kupala.contracts import Authenticator, IdentityProvider, PasswordHasher
from kupala.extensions import Extension
from kupala.utils import import_string


class AuthenticatorConfig(t.TypedDict):
    authenticator: str
    user_provider: str
    options: t.Optional[dict[str, t.Any]]


class AuthenticationExtension(Extension):
    def __init__(
        self,
        user_providers: dict[str, IdentityProvider],
        default_provider: str = "default",
        authenticators: dict[str, AuthenticatorConfig] = None,
    ) -> None:
        self.default_provider = default_provider
        self.user_providers = user_providers
        self.authenticators = authenticators or {}

    def register(self, app: App) -> None:
        for name, user_provider in self.user_providers.items():
            app.bind(f"user_provider.{name}", user_provider)

        for name, config in self.authenticators.items():
            app.singleton(
                f"authenticator.{name}",
                self.create_authenticator(
                    config["authenticator"],
                    config.get("user_provider", "default"),
                    config.get("options", {}),
                ),
                tags=["authenticator"],
            )

        app.alias(f"user_provider.{self.default_provider}", IdentityProvider)
        app.singleton(
            LoginManager,
            self.create_login_manager,
            aliases=[
                "login_manager",
                "login_manager.default",
            ],
        )

    def create_authenticator(
        self,
        klass: str,
        user_provider: str,
        options: dict = None,
    ) -> t.Callable[[App], Authenticator]:
        def factory(app: App) -> Authenticator:
            options_ = options or {}
            provider = app.get(f"user_provider.{user_provider}")
            cls = import_string(klass)
            return cls(provider, **options_)

        return factory

    def create_login_manager(
        self,
        user_provider: IdentityProvider,
        hasher: PasswordHasher,
    ) -> LoginManager:
        return LoginManager(user_provider, hasher)
