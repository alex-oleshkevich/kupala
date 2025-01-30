from __future__ import annotations

import typing


class AccessError(Exception):
    """Base class for all access errors."""


class AccessDeniedError(AccessError):
    """Raised when access is denied."""


Resource = typing.Any


class AccessContext(typing.Protocol): ...


class Rule(typing.Protocol):  # pragma: no cover
    """A rule that checks if a given context satisfies some condition."""

    def __call__(self, context: AccessContext, resource: Resource | None = None) -> bool: ...


class Guard:
    def check(self, context: AccessContext, rule: Rule, resource: Resource | None = None) -> bool:
        """Check if the given rule is satisfied in the current context."""
        return rule(context, resource)

    def check_or_raise(self, context: AccessContext, rule: Rule, resource: Resource | None = None) -> None:
        """Check if the given rule is satisfied in the current context, raise AccessDeniedError if not."""
        if not self.check(context, rule, resource):
            raise AccessDeniedError()
        return None


def any_of(*rules: Rule) -> Rule:
    """Create a rule that checks if any of the given rules are satisfied."""

    def rule(context: AccessContext, resource: Resource | None = None) -> bool:
        return any(rule(context, resource) for rule in rules)

    return rule


def all_of(*rules: Rule) -> Rule:
    """Create a rule that checks if all of the given rules are satisfied."""

    def rule(context: AccessContext, resource: Resource | None = None) -> bool:
        return all(rule(context, resource) for rule in rules)

    return rule


def none_of(*rules: Rule) -> Rule:
    """Create a rule that checks if none of the given rules are satisfied."""

    def rule(context: AccessContext, resource: Resource | None = None) -> bool:
        return not any(rule(context, resource) for rule in rules)

    return rule
