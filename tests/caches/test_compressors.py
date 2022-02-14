import pytest

from kupala.cache.compressors import CacheCompressor, LzmaCompressor, NullCompressor, ZlibCompressor

compressors = [
    NullCompressor(),
    ZlibCompressor(),
    LzmaCompressor(),
]


@pytest.mark.parametrize('compressor', compressors)
def test_compressors(compressor: CacheCompressor) -> None:
    expected = b'value'
    compressed = compressor.compress(expected)
    assert compressor.decompress(compressed) == expected
