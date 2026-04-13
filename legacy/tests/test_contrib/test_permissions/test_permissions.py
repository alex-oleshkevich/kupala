import dataclasses

import pytest

from kupala.contrib.permissions import (
    Permission,
    PermissionGroup,
    Role,
    get_defined_permission_groups,
    get_defined_permissions,
    get_defined_roles,
    has_permission,
)

admin_permission = Permission(id="admin", description="admin")
manager_permission = Permission(id="manager", description="manager")


@dataclasses.dataclass
class AccessContext:
    permissions: set[Permission]


def test_has_permission() -> None:
    context = AccessContext(permissions={admin_permission})
    rule = has_permission(admin_permission)
    assert rule(context) is True
    assert rule(AccessContext(permissions={manager_permission})) is False


class TestPermission:
    def test_stringify(self) -> None:
        permission = Permission(id="admin", name="Admin permission")
        assert str(permission) == "Admin permission"

        permission = Permission(id="admin", name="")
        assert str(permission) == "admin"

    def test_equals(self) -> None:
        permission = Permission(id="admin", name="Admin permission")
        permission2 = Permission(id="admin", name="")
        assert permission == permission2

        with pytest.raises(NotImplementedError):
            assert permission == 1

    def test_rule_protocol(self) -> None:
        permission = Permission(id="admin", name="Admin permission")
        assert permission(AccessContext(permissions={permission})) is True


class TestPermissionGroup:
    def test_permission_group(self) -> None:
        group = PermissionGroup(name="group", description="group1", permissions=[admin_permission, manager_permission])
        assert group.name == "group"
        assert group.description == "group1"
        assert admin_permission in group
        assert list(group) == [admin_permission, manager_permission]

    def test_nested_group(self) -> None:
        custom_permission = Permission(id="custom", description="custom")
        group = PermissionGroup(
            name="group",
            description="group1",
            permissions=[admin_permission, manager_permission],
            groups=[PermissionGroup(name="subgroup1", description="subgroup1", permissions=[custom_permission])],
        )
        assert custom_permission in group

    def test_iterable(self) -> None:
        custom_permission = Permission(id="custom", description="custom")
        group = PermissionGroup(
            name="group",
            description="group1",
            permissions=[admin_permission, manager_permission],
            groups=[PermissionGroup(name="subgroup1", description="subgroup1", permissions=[custom_permission])],
        )
        assert list(group) == [admin_permission, manager_permission, custom_permission]

    def test_stringify(self) -> None:
        group = PermissionGroup(name="subgroup1", description="subgroup1")
        assert str(group) == "subgroup1"

    def test_contains(self) -> None:
        permission_a = Permission(id="a")
        permission_b = Permission(id="b")
        group = PermissionGroup(name="subgroup1", permissions=[permission_a])
        assert permission_a in group
        assert permission_b not in group


class TestRole:
    def test_role(self) -> None:
        role = Role(id="role", description="role1")
        assert role.id == "role"
        assert role.description == "role1"
        assert list(role) == []

    def test_with_permissions(self) -> None:
        role = Role(id="role", description="role1", permissions=[admin_permission])
        assert admin_permission in role
        assert list(role) == [admin_permission]

    def test_with_group(self) -> None:
        group = PermissionGroup(name="group", description="group1", permissions=[admin_permission, manager_permission])
        role = Role(
            id="role",
            description="role1",
            groups=[group],
        )
        assert role.groups == [group]
        assert admin_permission in role
        assert list(role) == [admin_permission, manager_permission]

    def test_with_nested_role(self) -> None:
        role = Role(
            id="role",
            description="role1",
            roles=[
                Role(id="subrole", description="subrole1", permissions=[admin_permission, manager_permission]),
            ],
        )
        assert admin_permission in role
        assert list(role) == [admin_permission, manager_permission]

    def test_stringify(self) -> None:
        role_a = Role(id="role", name="Role")
        role_b = Role(id="role")
        assert str(role_a) == "Role"
        assert str(role_b) == "role"

    def test_contains(self) -> None:
        permission_a = Permission(id="a")
        permission_b = Permission(id="b")
        role = Role(id="role", name="Role", permissions=[permission_a])
        assert permission_a in role
        assert permission_b not in role


def test_get_defined_permissions() -> None:
    class Holder:
        admin = Permission(id="admin", description="admin")
        manager = Permission(id="manager", description="manager")

    permissions = [x.id for x in get_defined_permissions(Holder)]
    assert permissions == ["admin", "manager"]


def test_get_defined_permission_groups() -> None:
    group = PermissionGroup(name="admin", permissions=[])

    class Holder:
        admin = group

    groups = list(get_defined_permission_groups(Holder))
    assert groups == [group]


def test_get_defined_roles() -> None:
    role = Role(id="admin")

    class Holder:
        admin = role

    roles = list(get_defined_roles(Holder))
    assert roles == [role]
