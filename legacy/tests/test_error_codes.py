from kupala.error_codes import ErrorCode


class TestErrorCode:
    def test_str(self) -> None:
        code = ErrorCode("test", "Test error")
        assert str(code) == "Test error"

    def test_eq(self) -> None:
        code = ErrorCode("test", "Test error")
        assert code == "test"
        assert code == ErrorCode("test", "Test error")
        assert code != "unknown"
        assert code != ErrorCode("unknown", "Unknown error")

    def test_int_eq(self) -> None:
        code = ErrorCode[int](100, "Test error")
        assert code == 100
        assert code == ErrorCode[int](100, "Test error")
        assert code != 200
        assert code != ErrorCode[int](200, "Unknown error")
