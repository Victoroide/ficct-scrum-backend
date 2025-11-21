"""
Tests for organization permissions.
"""

import pytest
from rest_framework.test import APIRequestFactory

from apps.authentication.tests.factories import UserFactory
from apps.organizations.permissions import (
    CanManageMembers,
    IsOrganizationMember,
    IsOrganizationOwnerOrAdmin,
)
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)


@pytest.mark.django_db
@pytest.mark.permissions
class TestIsOrganizationMember:
    """Test IsOrganizationMember permission."""

    def test_member_has_permission(self):
        """Test organization member has permission."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsOrganizationMember()
        assert permission.has_object_permission(request, None, org) is True

    def test_non_member_no_permission(self):
        """Test non-member has no permission."""
        user = UserFactory()
        org = OrganizationFactory()

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsOrganizationMember()
        assert permission.has_object_permission(request, None, org) is False

    def test_inactive_member_no_permission(self):
        """Test inactive member has no permission."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, is_active=False)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsOrganizationMember()
        assert permission.has_object_permission(request, None, org) is False


@pytest.mark.django_db
@pytest.mark.permissions
class TestIsOrganizationOwnerOrAdmin:
    """Test IsOrganizationOwnerOrAdmin permission."""

    def test_owner_has_write_permission(self):
        """Test owner has write permission."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="owner")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsOrganizationOwnerOrAdmin()
        assert permission.has_object_permission(request, None, org) is True

    def test_admin_has_write_permission(self):
        """Test admin has write permission."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="admin")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsOrganizationOwnerOrAdmin()
        assert permission.has_object_permission(request, None, org) is True

    def test_member_no_write_permission(self):
        """Test regular member has no write permission."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="member")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsOrganizationOwnerOrAdmin()
        assert permission.has_object_permission(request, None, org) is False

    def test_member_has_read_permission(self):
        """Test regular member has read permission."""
        user = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=user, role="member")

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsOrganizationOwnerOrAdmin()
        assert permission.has_object_permission(request, None, org) is True


@pytest.mark.django_db
@pytest.mark.permissions
class TestCanManageMembers:
    """Test CanManageMembers permission."""

    def test_owner_can_manage_any_member(self):
        """Test owner can manage any member."""
        owner = UserFactory()
        org = OrganizationFactory()
        _owner_membership = OrganizationMembershipFactory(  # noqa: F841
            organization=org, user=owner, role="owner"
        )

        target_member = OrganizationMembershipFactory(organization=org, role="admin")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = owner

        permission = CanManageMembers()
        assert permission.has_object_permission(request, None, target_member) is True

    def test_admin_cannot_manage_owner(self):
        """Test admin cannot manage owner."""
        admin = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=admin, role="admin")

        owner_membership = OrganizationMembershipFactory(organization=org, role="owner")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = admin

        permission = CanManageMembers()
        assert (
            permission.has_object_permission(request, None, owner_membership) is False
        )

    def test_admin_cannot_manage_other_admins(self):
        """Test admin cannot manage other admins."""
        admin1 = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=admin1, role="admin")

        admin2_membership = OrganizationMembershipFactory(
            organization=org, role="admin"
        )

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = admin1

        permission = CanManageMembers()
        assert (
            permission.has_object_permission(request, None, admin2_membership) is False
        )

    def test_manager_can_only_manage_regular_members(self):
        """Test manager can only manage regular members."""
        manager = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=manager, role="manager")

        # Can manage regular member
        member_membership = OrganizationMembershipFactory(
            organization=org, role="member"
        )

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = manager

        permission = CanManageMembers()
        assert (
            permission.has_object_permission(request, None, member_membership) is True
        )

        # Cannot manage admin
        admin_membership = OrganizationMembershipFactory(organization=org, role="admin")
        assert (
            permission.has_object_permission(request, None, admin_membership) is False
        )

    def test_regular_member_cannot_manage(self):
        """Test regular member cannot manage anyone."""
        member = UserFactory()
        org = OrganizationFactory()
        OrganizationMembershipFactory(organization=org, user=member, role="member")

        target_member = OrganizationMembershipFactory(organization=org, role="member")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = member

        permission = CanManageMembers()
        assert permission.has_object_permission(request, None, target_member) is False
