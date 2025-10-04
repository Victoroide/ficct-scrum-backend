"""
Tests for workspace serializers.
"""
import pytest

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)
from apps.workspaces.serializers import WorkspaceMemberSerializer
from apps.workspaces.tests.factories import WorkspaceFactory


@pytest.mark.django_db
class TestWorkspaceMemberSerializer:
    """Test WorkspaceMemberSerializer."""

    def test_valid_workspace_member_creation(self):
        """Test creating workspace member with org member."""
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        user = UserFactory()

        # User must be org member first
        OrganizationMembershipFactory(organization=org, user=user)

        data = {"workspace": workspace.id, "user_id": str(user.id), "role": "member"}
        serializer = WorkspaceMemberSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_workspace_member_without_org_membership(self):
        """Test workspace member validation fails if not org member."""
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        user = UserFactory()

        # User is NOT an org member
        data = {"workspace": workspace.id, "user_id": str(user.id), "role": "member"}
        serializer = WorkspaceMemberSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors or "user_id" in serializer.errors

    def test_workspace_member_inactive_org_membership(self):
        """Test workspace member validation with inactive org membership."""
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        user = UserFactory()

        # User has inactive org membership
        OrganizationMembershipFactory(organization=org, user=user, is_active=False)

        data = {"workspace": workspace.id, "user_id": str(user.id), "role": "member"}
        serializer = WorkspaceMemberSerializer(data=data)
        assert not serializer.is_valid()
