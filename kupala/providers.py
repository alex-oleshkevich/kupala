import abc

from kupala.application import Kupala


class Provider(abc.ABC):
    def configure(self, app: Kupala) -> None:
        pass

    def register(self, app: Kupala) -> None:
        pass

    def bootstrap(self, app: Kupala) -> None:
        pass
