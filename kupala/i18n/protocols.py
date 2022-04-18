import typing


class HasPreferredLanguage(typing.Protocol):  # pragma: nocover
    """Defines an object that can provide preselected language information."""

    def get_preferred_language(self) -> str | None:
        ...


class HasTimezone(typing.Protocol):  # pragma: nocover
    """Defines an object that can provide a timezone."""

    def get_timezone(self) -> str | None:
        ...


class Translator:  # pragma: nocover
    def gettext(self, msg: str, **variables: typing.Any) -> str:
        ...

    def ngettext(self, /, singular: str, plural: str, count: int, **variables: typing.Any) -> str:
        ...
