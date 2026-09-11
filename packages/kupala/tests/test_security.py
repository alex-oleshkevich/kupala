import dataclasses

import pytest

import kupala
from kupala.security import Identity


class TestIdentity:
    def test_preserves_the_principal_and_granted_scopes(self) -> None:
        principal = object()

        identity: Identity[object] = Identity(principal, frozenset({"profile:read"}))

        assert identity.principal is principal
        assert identity.scopes == {"profile:read"}

    def test_defaults_to_no_granted_scopes(self) -> None:
        identity = Identity("alice")

        assert identity.scopes == frozenset()

    def test_is_frozen_and_slotted(self) -> None:
        identity = Identity("alice")

        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.__setattr__("principal", "bob")

        assert not hasattr(identity, "__dict__")

    def test_is_exported_from_the_public_package(self) -> None:
        assert kupala.Identity is Identity
