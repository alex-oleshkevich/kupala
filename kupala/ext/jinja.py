import typing

from kupala.application import App, Extension
from kupala.templating import ContextProcessor


def use_jinja_config(
    template_dirs: list[str] | None = None,
    packages: list[str] | None = None,
    filters: dict[str, typing.Any] | None = None,
    globals: dict[str, typing.Any] | None = None,
    policies: dict[str, typing.Any] | None = None,
    tests: dict[str, typing.Any] | None = None,
    extensions: list[str] | None = None,
    context_processors: list[ContextProcessor] | None = None,
) -> Extension:
    def extension(app: App) -> None:
        if template_dirs:
            app.add_template_directories(*template_dirs)
        if packages:
            app.add_template_packages(*packages)
        if filters:
            app.add_template_filters(**filters)
        if globals:
            app.add_template_global(**globals)
        if tests:
            app.add_template_tests(**tests)
        if policies:
            app.get_jinja_env().policies.update(policies or {})
        if extensions:
            app.add_template_extensions(*extensions)
        if context_processors:
            app.add_template_context_processors(*context_processors)

    return extension
