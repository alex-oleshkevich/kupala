import typing as t

from kupala.application import get_current_app
from kupala.authentication import LoginManager
from kupala.config import Config
from kupala.contracts import PasswordHasher, TemplateRenderer


def render_template(template: str, context: dict = None) -> str:
    return get_current_app().get(TemplateRenderer).render(template, context)


def config(key: str = None, default: t.Any = None) -> t.Union[t.Any, Config]:
    _config = get_current_app().get(Config)
    if key is not None:
        return _config.get(key, default)
    return _config


def password_hasher() -> PasswordHasher:
    return get_current_app().get(PasswordHasher)


def login_manager() -> LoginManager:
    return get_current_app().get(LoginManager)
