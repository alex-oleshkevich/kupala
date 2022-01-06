from __future__ import annotations

import typing

from kupala.contracts import PasswordHasher, TemplateRenderer
from kupala.utils import import_string

if typing.TYPE_CHECKING:
    from kupala.app.base import BaseApp


class Component:
    def initialize(self, app: BaseApp) -> None:
        pass


_PasswordHasherType = typing.Literal['pbkdf2_sha256', 'pbkdf2_sha512', 'argon2', 'bcrypt', 'des_crypt'] | PasswordHasher


class Passwords(Component):
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


class Renderer:
    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        self._template_renderer = renderer

    def use(self, renderer: TemplateRenderer) -> None:
        self._template_renderer = renderer

    def render(self, template_name: str, context: dict[str, typing.Any] = None) -> str:
        assert self._template_renderer, 'Template rendering is not configured.'
        return self._template_renderer.render(template_name, context)
