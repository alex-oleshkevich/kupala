import abc
import json
import pickle
import typing


class CacheSerializer(abc.ABC):  # pragma: no cover
    @abc.abstractmethod
    def dumps(self, value: typing.Any) -> bytes:
        ...

    @abc.abstractmethod
    def loads(self, value: bytes) -> typing.Any:
        ...


class JSONSerializer(CacheSerializer):
    def dumps(self, value: typing.Any) -> bytes:
        return json.dumps(value).encode()

    def loads(self, value: bytes) -> typing.Any:
        return json.loads(value)


class PickleSerializer(CacheSerializer):
    def dumps(self, value: typing.Any) -> bytes:
        return pickle.dumps(value)

    def loads(self, value: bytes) -> typing.Any:
        return pickle.loads(value)


class MsgpackSerializer(CacheSerializer):
    def dumps(self, value: typing.Any) -> bytes:
        import msgpack

        return msgpack.dumps(value)

    def loads(self, value: bytes) -> typing.Any:
        import msgpack

        return msgpack.loads(value, raw=False)
