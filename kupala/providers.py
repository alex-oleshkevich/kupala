import abc

from kupala.application import Kupala


class Provider(abc.ABC):
    def register(self, app: Kupala) -> None:
        pass

    def bootstrap(self, app: Kupala) -> None:
        pass
