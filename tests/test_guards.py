from unittest import mock

import pytest

from kupala.guards import AccessContext, AccessDeniedError, Guard, Resource, all_of, any_of, none_of


def true_rule(context: AccessContext, resource: Resource | None = None) -> bool:
    return True


def false_rule(context: AccessContext, resource: Resource | None = None) -> bool:
    return False


class TestGuard:
    def test_check(self) -> None:
        guard = Guard()
        assert guard.check(mock.MagicMock(), true_rule) is True

    def test_check_or_raise(self) -> None:
        guard = Guard()
        with pytest.raises(AccessDeniedError):
            guard.check_or_raise(mock.MagicMock(), false_rule)


def test_any_of() -> None:
    rule = any_of(true_rule, false_rule)
    assert rule(mock.MagicMock()) is True

    rule = any_of(true_rule, true_rule)
    assert rule(mock.MagicMock()) is True

    rule = any_of(false_rule, false_rule)
    assert rule(mock.MagicMock()) is False


def test_all_of() -> None:
    rule = all_of(true_rule, true_rule)
    assert rule(mock.MagicMock()) is True

    rule = all_of(true_rule, false_rule)
    assert rule(mock.MagicMock()) is False


def test_none_of() -> None:
    rule = none_of(false_rule, false_rule)
    assert rule(mock.MagicMock()) is True

    rule = none_of(true_rule, false_rule)
    assert rule(mock.MagicMock()) is False
