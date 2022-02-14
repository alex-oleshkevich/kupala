import pytest

from kupala.cache.serializers import CacheSerializer, JSONSerializer, MsgpackSerializer, PickleSerializer

serializers = [
    JSONSerializer(),
    PickleSerializer(),
    MsgpackSerializer(),
]


@pytest.mark.parametrize('serializer', serializers)
def test_json_serializer(serializer: CacheSerializer) -> None:
    expected = {'key': 'value'}
    serialized = serializer.dumps(expected)
    assert serializer.loads(serialized) == expected
