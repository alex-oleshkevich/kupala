import typing


class KupalaError(Exception):
    """Base class for all Kupala framework errors."""


class ValidationError(KupalaError):
    """Raised when data is not valid by any criteria."""

    def __init__(
        self,
        message: str = None,
        errors: typing.Mapping[str, list[str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


class StartupError(KupalaError):
    """
    Raised when application fails to start up (eg.

    lifespan handler raises error).
    """


class ShutdownError(KupalaError):
    """
    Raised when application fails to shutdown (eg.

    lifespan handler raises error).
    """
