from __future__ import annotations

import jinja2
import jinja2.ext
import logging
import os
import time
import typing
from email.message import Message
from functools import cached_property
from mailers import Email, Encrypter, Mailer, Plugin, SentMessages, Signer, create_transport_from_url

from kupala import json
from kupala.di import make_injectable
from kupala.storages.storages import LocalStorage, S3Storage, Storage
from kupala.templating import JinjaRenderer
from kupala.utils import resolve_path

if typing.TYPE_CHECKING:  # pragma: nocover
    from kupala.application import Kupala


class Extension:
    def initialize(self, app: Kupala) -> None:
        pass


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
        make_injectable(Mailer, from_app_factory=lambda app: self.get_default())

    async def send(self, message: Email | Message, mailer: str = None) -> SentMessages:
        mailer_name = mailer or self.default
        return await self.get(mailer_name).send(message)


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
        make_injectable(Storage, from_app_factory=lambda app: self.get_default())


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
        """
        Create and return instance of jinja2.BaseLoader.

        If no `loader` constructor argument passed then jinja2.FileSystemLoader
        will be used.
        """
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

            if 'json.dumps_function' not in env.policies:
                env.policies['json.dumps_function'] = json.dumps

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
        random_suffix: bool = True,
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
