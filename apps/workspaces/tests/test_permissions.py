"""
Tests for workspace permissions.
"""
import pytest
from rest_framework.test import APIRequestFactory

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)
from apps.workspaces.permissions import (
    CanAccessWorkspace,
    IsWorkspaceAdmin,
    IsWorkspaceMember,
)
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


@pytest.mark.django_db
@pytest.mark.permissions
class TestIsWorkspaceMember:
    """Test IsWorkspaceMember permission."""

    def test_workspace_member_has_permission(self):
        """Test workspace member has permission."""
        user = UserFactory()
        workspace = WorkspaceFactory()
        WorkspaceMemberFactory(workspace=workspace, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsWorkspaceMember()
        assert permission.has_object_permission(request, None, workspace) is True

    def test_non_member_no_permission(self):
        """Test non-workspace-member has no permission."""
        user = UserFactory()
        workspace = WorkspaceFactory()

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsWorkspaceMember()
        assert permission.has_object_permission(request, None, workspace) is False


@pytest.mark.django_db
@pytest.mark.permissions
class TestIsWorkspaceAdmin:
    """Test IsWorkspaceAdmin permission."""

    def test_workspace_admin_has_write_permission(self):
        """Test workspace admin has write permission."""
        user = UserFactory()
        workspace = WorkspaceFactory()
        WorkspaceMemberFactory(workspace=workspace, user=user, role="admin")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsWorkspaceAdmin()
        assert permission.has_object_permission(request, None, workspace) is True

    def test_regular_member_no_write_permission(self):
        """Test regular workspace member has no write permission."""
        user = UserFactory()
        workspace = WorkspaceFactory()
        WorkspaceMemberFactory(workspace=workspace, user=user, role="member")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsWorkspaceAdmin()
        assert permission.has_object_permission(request, None, workspace) is False

    def test_org_owner_has_workspace_admin_permission(self):
        """Test organization owner has workspace admin permission."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user, role="owner")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsWorkspaceAdmin()
        assert permission.has_object_permission(request, None, workspace) is True

    def test_org_admin_has_workspace_admin_permission(self):
        """Test organization admin has workspace admin permission."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user, role="admin")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsWorkspaceAdmin()
        assert permission.has_object_permission(request, None, workspace) is True


@pytest.mark.django_db
@pytest.mark.permissions
class TestCanAccessWorkspace:
    """Test CanAccessWorkspace permission."""

    def test_workspace_member_can_access(self):
        """Test workspace member can access."""
        user = UserFactory()
        workspace = WorkspaceFactory(visibility="private")
        WorkspaceMemberFactory(workspace=workspace, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessWorkspace()
        assert permission.has_object_permission(request, None, workspace) is True

    def test_org_member_can_read_public_workspace(self):
        """Test org member can read public workspace."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org, visibility="public")

        OrganizationMembershipFactory(organization=org, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessWorkspace()
        assert permission.has_object_permission(request, None, workspace) is True

    def test_org_member_cannot_write_public_workspace(self):
        """Test org member cannot write to public workspace without membership."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org, visibility="public")

        OrganizationMembershipFactory(organization=org, user=user)

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = CanAccessWorkspace()
        assert permission.has_object_permission(request, None, workspace) is False

    def test_org_member_cannot_access_private_workspace(self):
        """Test org member cannot access private workspace without membership."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org, visibility="private")

        OrganizationMembershipFactory(organization=org, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessWorkspace()
        assert permission.has_object_permission(request, None, workspace) is False

    def test_org_admin_can_access_restricted_workspace(self):
        """Test org admin can access restricted workspace."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org, visibility="restricted")

        OrganizationMembershipFactory(organization=org, user=user, role="admin")

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessWorkspace()
        assert permission.has_object_permission(request, None, workspace) is True
