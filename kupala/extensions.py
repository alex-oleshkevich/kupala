from __future__ import annotations

import click
import itsdangerous.signer
import jinja2
import jinja2.ext
import logging
import os
import time
import typing
from click.testing import CliRunner
from email.message import Message
from functools import cached_property
from imia import BaseAuthenticator, LoginManager, UserProvider, UserToken
from mailers import Email, Encrypter, Mailer, Plugin, SentMessages, Signer, create_transport_from_url

from kupala.console.application import ConsoleApplication
from kupala.contracts import PasswordHasher, TemplateRenderer
from kupala.di import to_app_injectable, to_request_injectable
from kupala.storages.storages import LocalStorage, S3Storage, Storage
from kupala.templating import JinjaRenderer
from kupala.utils import import_string, resolve_path

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.application import Kupala


class Extension:
    def initialize(self, app: Kupala) -> None:
        pass


_PasswordHasherType = typing.Literal['pbkdf2_sha256', 'pbkdf2_sha512', 'argon2', 'bcrypt', 'des_crypt'] | PasswordHasher


class PasswordsExtension(Extension):
    def __init__(self, backend: _PasswordHasherType = 'pbkdf2_sha256') -> None:
        self._manager = self._create(backend)

    def hash(self, plain_password: str) -> str:
        return self._manager.hash(plain_password)

    def verify(self, plain: str, hashed: str) -> bool:
        return self._manager.verify(plain, hashed)

    def use(self, backend: _PasswordHasherType) -> None:
        self._manager = self._create(backend)

    def _create(self, backend: _PasswordHasherType) -> PasswordHasher:
        if isinstance(backend, str):
            imports = {
                'pbkdf2_sha256': 'passlib.handlers.pbkdf2:pbkdf2_sha256',
                'pbkdf2_sha512': 'passlib.handlers.pbkdf2:pbkdf2_sha512',
                'argon2': 'passlib.handlers.argon2:argon2',
                'bcrypt': 'passlib.handlers.bcrypt:bcrypt',
                'des_crypt': 'passlib.handlers.des_crypt:des_crypt',
            }
            backend = typing.cast(PasswordHasher, import_string(imports[backend]))
        return backend

    def initialize(self, app: Kupala) -> None:
        app.di.prefer_for(PasswordHasher, lambda app: self._manager)


class RendererExtension(Extension):
    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        self._template_renderer = renderer

    def use(self, renderer: TemplateRenderer) -> None:
        self._template_renderer = renderer

    def render(self, template_name: str, context: dict[str, typing.Any] = None) -> str:
        assert self._template_renderer, 'Template rendering is not configured.'
        return self._template_renderer.render(template_name, context)


class MailExtension(Extension):
    def __init__(self, mailers: dict[str, Mailer] = None, default: str = 'default') -> None:
        self.default = default
        self._mailers: dict[str, Mailer] = mailers or {}

    def get(self, name: str) -> Mailer:
        if name not in self._mailers:
            raise KeyError(f'No mailer named "{name}" defined.')
        return self._mailers[name]

    def use(
        self,
        url: str,
        *,
        from_address: str = 'no-reply@example.com',
        from_name: str = 'Example',
        signer: Signer = None,
        encrypter: Encrypter = None,
        plugins: list[Plugin] = None,
        name: str = 'default',
    ) -> None:
        if from_name:
            from_address = f'{from_name} <{from_address}>'
        transport = create_transport_from_url(url)
        self.add(
            name,
            Mailer(
                transport,
                from_address=from_address,
                plugins=plugins,
                signer=signer,
                encrypter=encrypter,
            ),
        )

    def add(self, name: str, mailer: Mailer) -> None:
        assert name not in self._mailers, f'"{name}" already exists.'
        self._mailers[name] = mailer

    def get_default(self) -> Mailer:
        return self.get(self.default)

    def initialize(self, app: Kupala) -> None:
        to_app_injectable(Mailer, lambda app: self.get_default())

    async def send(self, message: Email | Message, mailer: str = None) -> SentMessages:
        mailer_name = mailer or self.default
        return await self.get(mailer_name).send(message)


class AuthenticationExtension(Extension):
    def __init__(self, app: Kupala) -> None:
        self.user_model: typing.Type[typing.Any] | None = None
        self.user_provider: UserProvider | None = None
        self.authenticators: list[BaseAuthenticator] = []
        self.password_verifier = app.passwords
        self.secret_key = app.secret_key

    @property
    def login_manager(self) -> LoginManager:
        assert self.user_provider, 'Authentication component requires user provider to be configured.'
        return LoginManager(
            user_provider=self.user_provider,
            password_verifier=self.password_verifier,
            secret_key=self.secret_key,
        )

    def configure(
        self,
        user_model: typing.Type[typing.Any] = None,
        user_provider: UserProvider | None = None,
        authenticators: list[BaseAuthenticator] | None = None,
    ) -> None:
        """Configure multiple options at once."""
        if user_model:
            self.user_model = user_model
        if user_provider:
            self.user_provider = user_provider
        if authenticators:
            self.authenticators = authenticators

    def initialize(self, app: Kupala) -> None:
        to_app_injectable(LoginManager, lambda app: self.login_manager)
        to_request_injectable(UserToken, lambda request: request.auth)


class StoragesExtension(Extension):
    def __init__(self, storages: dict[str, Storage] = None, default: str = 'default') -> None:
        self.default = default
        self._storages: dict[str, Storage] = storages or {}

    def get(self, name: str) -> Storage:
        if name not in self._storages:
            raise KeyError(f'No storage named "{name}" defined.')
        return self._storages[name]

    def get_default(self) -> Storage:
        if self.default in self._storages:
            return self._storages[self.default]
        if len(self._storages) == 1:
            return list(self._storages.values())[0]
        raise KeyError('No default storage configured.')

    def add(self, name: str, storage: Storage) -> None:
        self._storages[name] = storage

    def add_local(self, name: str, base_dir: str | os.PathLike) -> None:
        self.add(name, LocalStorage(base_dir))

    def add_s3(
        self,
        name: str,
        bucket: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str = None,
        profile_name: str = None,
        endpoint_url: str = None,
        link_ttl: int = 300,
    ) -> None:
        self.add(
            name,
            S3Storage(
                bucket=bucket,
                aws_secret_access_key=aws_secret_access_key,
                aws_access_key_id=aws_access_key_id,
                region_name=region_name,
                profile_name=profile_name,
                endpoint_url=endpoint_url,
                link_ttl=link_ttl,
            ),
        )

    def initialize(self, app: Kupala) -> None:
        to_app_injectable(Storage, lambda app: self.get_default())


class JinjaExtension(Extension):
    def __init__(
        self,
        template_dirs: str | list[str] | None = None,
        tests: dict[str, typing.Callable] = None,
        filters: dict[str, typing.Callable] = None,
        globals: dict[str, typing.Any] = None,
        policies: dict[str, typing.Any] = None,
        extensions: list[str | typing.Type[jinja2.ext.Extension]] = None,
        env: jinja2.Environment = None,
        loader: jinja2.BaseLoader = None,
    ) -> None:
        self.template_dirs = [template_dirs] if isinstance(template_dirs, str) else template_dirs or []
        self.tests = tests or {}
        self.filters = filters or {}
        self.globals = globals or {}
        self.policies = policies or {}
        self.extensions = extensions or []
        self._env = env
        self._loader = loader

    @property
    def loader(self) -> jinja2.BaseLoader:
        """Create and return instance of jinja2.BaseLoader.
        If no `loader` constructor argument passed then jinja2.FileSystemLoader will be used."""
        if self._loader is None:
            self._loader = jinja2.FileSystemLoader(
                searchpath=[resolve_path(directory) for directory in self.template_dirs]
            )
        return self._loader

    @property
    def env(self) -> jinja2.Environment:
        """Create and return jinja2.Environment instance."""
        if self._env is None:
            env = jinja2.Environment(loader=self.loader, extensions=self.extensions)
            env.globals.update(self.globals)
            env.filters.update(self.filters)
            env.policies.update(self.policies)
            env.tests.update(self.tests)

            if "json.dumps_kwargs" not in env.policies:
                env.policies["json.dumps_kwargs"] = {"ensure_ascii": False, "sort_keys": True}
            self._env = env
        return self._env

    @cached_property
    def renderer(self) -> JinjaRenderer:
        """Create and return Jinja template renderer."""
        return JinjaRenderer(self.env)

    def use_loader(self, loader: jinja2.BaseLoader) -> None:
        """Use custom template loader."""
        self._loader = loader

    def use_env(self, env: jinja2.Environment) -> None:
        """Use preconfigured loader."""
        self._env = env

    def add_template_dirs(self, directories: list[str | os.PathLike] | str | os.PathLike) -> None:
        """Add additional directories for template search."""
        if isinstance(directories, (str, os.PathLike)):
            directories = [directories]

        if isinstance(self.env.loader, jinja2.FileSystemLoader):
            self.env.loader.searchpath = [resolve_path(str(directory)) for directory in directories]
        else:  # pragma: nocover
            logging.warning('Hot directory update supported only for jinja2.FileSystemLoader loader.')

    def add_globals(self, globals: dict[str, typing.Any]) -> None:
        """Add global variables to jinja environment."""
        self.env.globals.update(globals)

    def add_filters(self, filters: dict[str, typing.Callable]) -> None:
        """Add filters to jinja environment."""
        self.env.filters.update(filters)

    def add_policies(self, policies: dict[str, typing.Any]) -> None:
        """Add policies to jinja environment."""
        self.env.policies.update(policies)

    def add_tests(self, tests: dict[str, typing.Any]) -> None:
        """Add tests to jinja environment."""
        self.env.tests.update(tests)

    def add_extensions(self, *extension: str | typing.Type[jinja2.ext.Extension]) -> None:
        """Add extension to jinja environment."""
        for _extension in extension:
            self.env.add_extension(_extension)

    def configure(
        self,
        template_dirs: list[str | os.PathLike] = None,
        globals: dict[str, typing.Any] = None,
        filters: dict[str, typing.Callable] = None,
        policies: dict[str, typing.Any] = None,
        tests: dict[str, typing.Any] = None,
        extensions: list[str | typing.Type[jinja2.ext.Extension]] = None,
    ) -> None:
        """Configure multiple options at once."""
        if template_dirs:
            self.add_template_dirs(template_dirs)
        if globals:
            self.add_globals(globals)
        if filters:
            self.add_filters(filters)
        if policies:
            self.add_policies(policies)
        if tests:
            self.add_tests(tests)
        if extensions:
            self.add_extensions(*extensions)


class SignerExtension(Extension):
    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key

    def initialize(self, app: Kupala) -> None:
        to_app_injectable(itsdangerous.signer.Signer, lambda app: self.signer)
        to_app_injectable(itsdangerous.timed.TimestampSigner, lambda app: self.timestamp_signer)

    @cached_property
    def signer(self) -> itsdangerous.signer.Signer:
        return itsdangerous.signer.Signer(self.secret_key)

    @cached_property
    def timestamp_signer(self) -> itsdangerous.timed.TimestampSigner:
        return itsdangerous.timed.TimestampSigner(self.secret_key)

    def sign(self, value: str | bytes) -> bytes:
        """Sign value."""
        return self.signer.sign(value)

    def unsign(self, signed_value: str | bytes) -> bytes:
        """Unsign value. Raises itsdangerous.BadSignature exception."""
        return self.signer.unsign(signed_value)

    def safe_unsign(self, signed_value: str | bytes) -> tuple[bool, typing.Optional[bytes]]:
        """Unsign value. Will not raise itsdangerous.BadSignature.
        Returns two-tuple: operation status and unsigned value."""
        try:
            return True, self.unsign(signed_value)
        except itsdangerous.BadSignature:
            return False, None

    def timed_sign(self, value: str | bytes) -> bytes:
        """Sign value. The signature will be valid for a specific time period."""
        return self.timestamp_signer.sign(value)

    def timed_unsign(self, signed_value: str | bytes, max_age: int) -> bytes:
        """Unsign value. Will raise itsdangerous.BadSignature or itsdangerous.BadTimeSignature exception
        if signed value cannot be decoded or expired.."""
        return self.timestamp_signer.unsign(signed_value, max_age)

    def safe_timed_unsign(self, signed_value: str | bytes, max_age: int) -> tuple[bool, typing.Optional[bytes]]:
        """Unsign value. Will not raise itsdangerous.BadTimeSignature.
        Returns two-tuple: operation status and unsigned value."""
        try:
            return True, self.timed_unsign(signed_value, max_age)
        except itsdangerous.BadSignature:
            return False, None


class ConsoleExtension:
    def __init__(self, app: Kupala, commands: list[click.Command] = None) -> None:
        self.app = app
        self.commands = commands or []

    @property
    def test_runner(self) -> CliRunner:
        return CliRunner()

    def add(self, *command: click.Command) -> None:
        self.commands.extend(command)

    def run(self) -> int:
        app = ConsoleApplication(self.app, self.commands)
        return app.run()

    def __iter__(self) -> typing.Iterator[click.Command]:
        return iter(self.commands)


class StaticFilesExtension(Extension):
    """Configures static files endpoint."""

    def __init__(self, app: Kupala) -> None:
        self.app = app
        self.start_time = time.time()

    def serve_from_directory(
        self,
        directory: str | os.PathLike = 'statics',
        url_path: str = '/static',
        url_prefix: str = '',
        storage_name: str = 'static',
        path_name: str = 'static',
        random_suffix: bool = False,
    ) -> None:
        assert self.app, 'Unbound StaticFiles instance.'
        self.url_prefix = url_prefix
        self.path_name = path_name
        self.random_suffix = random_suffix
        self.app.storages.add_local(storage_name, directory)
        self.app.routes.files(url_path, storage=storage_name, name=path_name, inline=False)
        self.app.jinja.add_globals({"static": self.static_url})

    def static_url(self, path: str | os.PathLike) -> str:
        router = self.app.get_asgi_app().router
        url = str(router.url_path_for(self.path_name, path=str(path)))
        if not url.startswith('http') and self.url_prefix:
            url = self.url_prefix.rstrip('/') + url

        if self.random_suffix:
            url += '?' + str(self.start_time)
        return url


class URLExtension(Extension):
    def __init__(self, app: Kupala) -> None:
        self._app = app

    def url_for(self, path_name: str, **params: str) -> str:
        return self._app.get_asgi_app().router.url_path_for(path_name, **params)
