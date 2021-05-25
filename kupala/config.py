from __future__ import annotations

import copy
import typing as t


class ConfigError(Exception):
    """Base exception for all config related errors."""


class LockedError(ConfigError):
    """Raised when the configuration object is locked."""


class Config:
    """Keeps application configuration three."""

    def __init__(self, initial: dict = None) -> None:
        self._data = initial or {}
        self._is_locked = False

    def get(self, key: str, default: t.Any = None, dotpath: bool = True) -> t.Any:
        """Get a value from the configuration object.
        If the resolved value is missing on the object,
        the `default` will be returned.

        If the `key` contains dot '.' then the config will look up
        recursively. For example, for key "application.debug" the lookup will
        look like this: config['application']['debug'].
        You can disable this behavior by setting `dotpath` to False.

        This method returns a deep copy of the found value."""
        if dotpath:
            segments = key.split(".")
            value = self._data
            for segment in segments:
                if segment in value:
                    value = value[segment]
                else:
                    return default
        else:
            value = self._data.get(key, default)
        return copy.deepcopy(value)

    def set(self, section: str, data: t.Any) -> None:
        """Set a value for a section.
        Raises LockedError if the config object locked."""
        self._raise_if_locked()
        self._data[section] = data

    def merge(self, section: str, data: t.Any) -> None:
        """Merge data into a section.
        If section is missing it will be created.
        Raises LockedError if the config object locked."""
        self._data.setdefault(section, {})
        value = self._data[section]
        value.update(data)
        self._data[section] = value

    def update(self, data: t.Any) -> None:
        """Update configuration object.
        This method behaves as dict.update..
        Raises LockedError if the config object locked."""
        self._raise_if_locked()
        self._data.update(data)

    def delete(self, section: str) -> None:
        """Delete configuration section from the object.
        Raises LockedError if the config object locked."""
        self._raise_if_locked()
        if section in self._data:
            del self._data[section]

    def contains(self, section: str) -> bool:
        """Test if a config object contains a given section."""
        return section in self._data

    def setdefault(self, section: str, data: t.Any) -> None:
        """Set a default value for a section."""
        self._data.setdefault(section, data)

    def lock(self) -> None:
        """Lock the config.
        Once locked no config modification allowed.
        Any attempt will raise LockedError."""
        self._is_locked = True

    def unlock(self) -> _Lock:
        """Unlock (or temporary unlock) the config.

        In order to temporary unlock the object
        use it as a context manager:
            with config.unlock() as config:
                config.set('section', 'value')
        """
        self._is_locked = False
        return _Lock(self)

    def _raise_if_locked(self) -> None:
        """Checks if the object is locked and raises LockedError when True."""
        if self._is_locked:
            raise LockedError("The config object is locked. No modifications possible.")

    def __repr__(self) -> str:  # pragma: nocover
        return "<Config: keys=%s>" % self._data.keys()

    __getitem__ = get
    __setitem__ = set
    __delitem__ = delete
    __contains__ = contains
    __call__ = get


class _Lock:
    def __init__(self, config: Config) -> None:
        self._config = config

    def __enter__(self) -> Config:
        return self._config

    def __exit__(self, *args: t.Any) -> None:
        self._config.lock()
