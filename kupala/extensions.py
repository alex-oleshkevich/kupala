from __future__ import annotations

import jinja2
import jinja2.ext
import os
import typing
from functools import cached_property
from imia import BaseAuthenticator, LoginManager, UserProvider
from mailers import Encrypter, Mailer, Plugin, Signer, create_transport_from_url

from kupala.contracts import PasswordHasher, TemplateRenderer
from kupala.storages.storages import LocalStorage, S3Storage, Storage
from kupala.templating import JinjaRenderer
from kupala.utils import import_string, resolve_path

if typing.TYPE_CHECKING:
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
            return import_string(imports[backend])
        return backend


class RendererExtension(Extension):
    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        self._template_renderer = renderer

    def use(self, renderer: TemplateRenderer) -> None:
        self._template_renderer = renderer

    def render(self, template_name: str, context: dict[str, typing.Any] = None) -> str:
        assert self._template_renderer, 'Template rendering is not configured.'
        return self._template_renderer.render(template_name, context)


class MailExtension(Extension):
    def __init__(self) -> None:
        self._mailers: dict[str, Mailer] = {}

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
        encrypter: Encrypter,
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
        self._mailers[name] = mailer


class AuthenticationExtension(Extension):
    def __init__(self, app: Kupala) -> None:
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


class StoragesExtension(Extension):
    def __init__(self, storages: dict[str, Storage] = None) -> None:
        self.default = 'default'
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

    @cached_property
    def loader(self) -> jinja2.BaseLoader:
        if self._loader:
            return self._loader
        return jinja2.FileSystemLoader(searchpath=[resolve_path(directory) for directory in self.template_dirs])

    @cached_property
    def env(self) -> jinja2.Environment:
        if self._env:
            return self._env
        env = jinja2.Environment(loader=self.loader, extensions=self.extensions)
        env.globals.update(self.globals)
        env.filters.update(self.filters)
        env.policies.update(self.policies)
        env.tests.update(self.tests)

        if "json.dumps_kwargs" not in env.policies:
            env.policies["json.dumps_kwargs"] = {"ensure_ascii": False, "sort_keys": True}

        return env

    @property
    def renderer(self) -> JinjaRenderer:
        return JinjaRenderer(self.env)
