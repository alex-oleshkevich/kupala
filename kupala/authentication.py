import typing as t
from dataclasses import dataclass

from kupala.contracts import Identity


@dataclass
class AuthState:
    user: t.Optional[Identity] = None

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None

    def clear(self) -> None:
        self.user = None

    def __bool__(self) -> bool:
        return self.is_authenticated

    def __eq__(self, other: Identity) -> bool:  # type: ignore[override]
        if self.user is None:
            return False
        return other.get_id() == self.user.get_id()
