import abc
import lzma
import zlib


class CacheCompressor(abc.ABC):  # pragma: no cover
    @abc.abstractmethod
    def compress(self, value: bytes) -> bytes:
        ...

    @abc.abstractmethod
    def decompress(self, value: bytes) -> bytes:
        ...


class NullCompressor(CacheCompressor):
    def compress(self, value: bytes) -> bytes:
        return value

    def decompress(self, value: bytes) -> bytes:
        return value


class ZlibCompressor(CacheCompressor):
    def __init__(self, level: int = -1) -> None:
        self.level = level

    def compress(self, value: bytes) -> bytes:
        return zlib.compress(value, level=self.level)

    def decompress(self, value: bytes) -> bytes:
        return zlib.decompress(value)


class LzmaCompressor(CacheCompressor):
    def __init__(self, min_length: int = 128, preset: int = 4) -> None:
        self.min_length = min_length
        self.preset = preset

    def compress(self, value: bytes) -> bytes:
        if len(value) > self.min_length:
            return lzma.compress(value, preset=self.preset)
        return value

    def decompress(self, value: bytes) -> bytes:
        try:
            return lzma.decompress(value)
        except lzma.LZMAError:  # small values are not compressed causing decoder to fail
            return value
