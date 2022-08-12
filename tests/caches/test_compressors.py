import pytest

from kupala.cache.compressors import CacheCompressor, LzmaCompressor, NullCompressor, ZlibCompressor

compressors = [
    NullCompressor(),
    ZlibCompressor(),
    LzmaCompressor(),
]


@pytest.mark.parametrize("compressor", compressors)
def test_compressors(compressor: CacheCompressor) -> None:
    expected = b"value" * 100
    compressed = compressor.compress(expected)
    assert compressor.decompress(compressed) == expected


def test_lzma_does_not_compress_small_values() -> None:
    compressor = LzmaCompressor()
    assert compressor.compress(b"bit") == b"bit"


def test_lzma_decompress_small_values_handled() -> None:
    compressor = LzmaCompressor()
    assert compressor.decompress(b"bit") == b"bit"
