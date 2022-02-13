from __future__ import annotations

import jinja2.ext
import os
import typing
from imia import LoginManager, UserProvider
from mailers import Mailer

from kupala.application import Kupala
from kupala.contracts import PasswordHasher, TemplateRenderer
from kupala.di import make_injectable
from kupala.i18n import formatters
from kupala.mails import MailerManager
from kupala.storages.storages import Storage, StorageManager
from kupala.templating import JinjaRenderer
from kupala.utils import import_string


def setup_authentication(app: Kupala, user_provider: UserProvider) -> None:
    app.state.login_manager = LoginManager(
        user_provider,
        password_verifier=app.state.password_hasher,
        secret_key=app.secret_key,
    )
    make_injectable(LoginManager, from_app_factory=lambda app: app.state.login_manager)


def setup_passwords(
    app: Kupala,
    hasher: typing.Literal['pbkdf2_sha256', 'pbkdf2_sha512', 'argon2', 'bcrypt', 'des_crypt'] | PasswordHasher,
) -> None:
    if isinstance(hasher, str):
        imports = {
            'pbkdf2_sha256': 'passlib.handlers.pbkdf2:pbkdf2_sha256',
            'pbkdf2_sha512': 'passlib.handlers.pbkdf2:pbkdf2_sha512',
            'argon2': 'passlib.handlers.argon2:argon2',
            'bcrypt': 'passlib.handlers.bcrypt:bcrypt',
            'des_crypt': 'passlib.handlers.des_crypt:des_crypt',
        }
        hasher = typing.cast(PasswordHasher, import_string(imports[hasher]))
    app.state.password_hasher = hasher
    app.di.prefer_for(PasswordHasher, lambda app: app.state.password_hasher)


class _TemplateRendererConfig:
    def __init__(self, app: Kupala) -> None:
        self.app = app

    def use_jinja(
        self,
        template_dirs: str | os.PathLike | list[str | os.PathLike],
        tests: dict[str, typing.Callable] = None,
        filters: dict[str, typing.Callable] = None,
        globals: dict[str, typing.Any] = None,
        policies: dict[str, typing.Any] = None,
        extensions: list[str | typing.Type[jinja2.ext.Extension]] = None,
        env: jinja2.Environment | None = None,
        loader: jinja2.BaseLoader | None = None,
    ) -> _TemplateRendererConfig:
        assert not all([template_dirs, loader]), '"template_dirs" and "loader" are mutually exclusive.'

        if env:
            self.app.jinja_env = env

        if loader:
            self.app.jinja_env.loader = loader
        elif template_dirs:
            template_dirs = [template_dirs] if isinstance(template_dirs, (str, os.PathLike)) else template_dirs
            self.app.jinja_env.loader = jinja2.ChoiceLoader(
                [
                    jinja2.PackageLoader('kupala'),
                    jinja2.FileSystemLoader(template_dirs),
                ]
            )

        # set user defined options
        self.app.jinja_env.tests.update(tests or {})
        self.app.jinja_env.policies.update(policies or {})
        self.app.jinja_env.globals.update(globals or {})
        self.app.jinja_env.filters.update(filters or {})
        for extension in extensions or []:
            self.app.jinja_env.add_extension(extension)

        self.app.set_renderer(JinjaRenderer(self.app.jinja_env))
        return self


def setup_renderer(app: Kupala, renderer: TemplateRenderer | None = None) -> _TemplateRendererConfig:
    if renderer:
        app.set_renderer(renderer)
    return _TemplateRendererConfig(app)


def setup_storages(
    app: Kupala,
    storages: dict[str, Storage] | None = None,
    default_storage: str = 'default',
) -> StorageManager:
    app.state.storages = StorageManager(storages, default_storage)
    return app.state.storages


def setup_mailers(
    app: Kupala, mailers: dict[str, Mailer] | None = None, default_mailer: str = 'default'
) -> MailerManager:
    app.state.mailers = MailerManager(mailers, default_mailer)
    return app.state.mailers


def setup_i18n(app: Kupala) -> None:
    if hasattr(app.state, 'jinja_env'):
        app.state.jinja_env.add_extension('jinja2.ext.i18n')
        app.state.jinja_env.globals.update(
            {
                '_': lambda x: x,
            }
        )
        app.state.jinja_env.filters.update(
            {
                'datetime': formatters.format_datetime,
                'date': formatters.format_date,
                'time': formatters.format_time,
                'timedelta': formatters.format_timedelta,
                'number': formatters.format_number,
                'currency': formatters.format_currency,
                'percent': formatters.format_percent,
                'scientific': formatters.format_scientific,
            }
        )
