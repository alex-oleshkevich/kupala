import typing as t
from dataclasses import dataclass, field

if t.TYPE_CHECKING:
    from kupala.application import App


class Extension(t.Protocol):
    def register(self, app: "App") -> None:
        pass

    def bootstrap(self, app: "App") -> None:
        pass


class BaseExtension:
    def register(self, app: "App") -> None:
        pass

    def bootstrap(self, app: "App") -> None:
        pass


@dataclass
class Extensions:
    _extensions: list[Extension] = field(default_factory=list)

    def use(self, extension: Extension) -> None:
        self._extensions.append(extension)

    def __iter__(self) -> t.Iterator[Extension]:
        return iter(self._extensions)
