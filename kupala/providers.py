import abc

from kupala.application import Kupala
from kupala.container import Container


class Provider(abc.ABC):
    def register(self, app: Kupala) -> None:
        pass

    def bootstrap(self, container: Container) -> None:
        pass
