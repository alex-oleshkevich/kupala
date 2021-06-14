import typing as t

from kupala.application import get_current_app
from kupala.config import Config
from kupala.contracts import PasswordHasher, TemplateRenderer, URLResolver


def render_template(template: str, context: dict = None) -> str:
    """Render template to string."""
    return get_current_app().get(TemplateRenderer).render(template, context)


def config(key: str = None, default: t.Any = None) -> t.Union[t.Any, Config]:
    """Access application's configuration.
    If no arguments passed then Config instance returned
    otherwise a configuration value specified by `key` returned."""
    _config = get_current_app().get(Config)
    if key is not None:
        return _config.get(key, default)
    return _config


def make_password(raw_password: str) -> str:
    """Encrypt raw password using configured password hasher."""
    return get_current_app().get(PasswordHasher).hash(raw_password)


def url_for(route_name: str, **path_params: str) -> str:
    """Generate URL for a route name."""
    return get_current_app().get(URLResolver).resolve(route_name, **path_params)
