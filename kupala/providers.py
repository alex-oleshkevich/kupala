import abc

from kupala.container import Container


class Provider(abc.ABC):
    def register(self, container: Container) -> None:
        pass

    def bootstrap(self, container: Container) -> None:
        pass
