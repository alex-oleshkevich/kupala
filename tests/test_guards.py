from unittest import mock

import pytest

from kupala.guards import AccessDeniedError, Guard, all_of, any_of, none_of


class TestGuard:
    def test_check(self) -> None:
        guard = Guard()
        assert guard.check(mock.MagicMock(), lambda c, r: True) is True  # type: ignore[arg-type]

    def test_check_or_raise(self) -> None:
        guard = Guard()
        with pytest.raises(AccessDeniedError):
            guard.check_or_raise(mock.MagicMock(), lambda c, r: False)  # type: ignore[arg-type]


def test_any_of() -> None:
    rule = any_of(lambda c, r: True, lambda c, r: False)
    assert rule(mock.MagicMock()) is True

    rule = any_of(lambda c, r: True, lambda c, r: True)
    assert rule(mock.MagicMock()) is True

    rule = any_of(lambda c, r: False, lambda c, r: False)
    assert rule(mock.MagicMock()) is False


def test_all_of() -> None:
    rule = all_of(lambda c, r: True, lambda c, r: True)
    assert rule(mock.MagicMock()) is True

    rule = all_of(lambda c, r: True, lambda c, r: False)
    assert rule(mock.MagicMock()) is False


def test_none_of() -> None:
    rule = none_of(lambda c, r: False, lambda c, r: False)
    assert rule(mock.MagicMock()) is True

    rule = none_of(lambda c, r: True, lambda c, r: False)
    assert rule(mock.MagicMock()) is False
