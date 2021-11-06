from __future__ import annotations

import copy
import typing as t


class ConfigError(Exception):
    """Base exception for all config related errors."""


class LockedError(ConfigError):
    """Raised when the configuration object is locked."""


class Config:
    """Keeps application configuration three."""

    def __init__(self, initial: t.Mapping = None) -> None:
        self._data = dict(initial or {})
        self._is_locked = False

    def get(self, key: str, default: t.Any = None) -> t.Any:
        """Get a value from the configuration object using dot-notation.
        This method returns a deep copy of the found value."""
        value = self._data
        for segment in key.split("."):
            if segment in value:
                value = value[segment]
            else:
                return default
        return copy.deepcopy(value)

    def get_key(self, key: str, default: t.Any = None) -> t.Any:
        """Get a value by a key."""
        return copy.deepcopy(self._data.get(key, default))

    def set(self, section: str, data: t.Any) -> None:
        """Set a value for a section.
        Raises LockedError if the config object locked."""
        self._raise_if_locked()
        self._data[section] = data

    def update(self, data: t.Any) -> None:
        """Update configuration object.

        This method behaves as dict.update..
        Raises LockedError if the config object locked."""
        self._raise_if_locked()
        self._data.update(data)

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
    __call__ = get


class _Lock:
    def __init__(self, config: Config) -> None:
        self._config = config

    def __enter__(self) -> Config:
        return self._config

    def __exit__(self, *args: t.Any) -> None:
        self._config.lock()
