import abc
import json
import typing


class CacheSerializer(abc.ABC):
    @abc.abstractmethod
    def serialize(self, value: typing.Any) -> bytes:
        pass

    @abc.abstractmethod
    def deserialize(self, value: bytes) -> typing.Any:
        pass


class JsonCacheSerializer(CacheSerializer):
    def serialize(self, value: typing.Any) -> bytes:
        return json.dumps(value).encode()

    def deserialize(self, value: bytes) -> typing.Any:
        return json.loads(value)
