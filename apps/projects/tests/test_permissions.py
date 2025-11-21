"""
Tests for project permissions.
"""

import pytest
from rest_framework.test import APIRequestFactory

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)
from apps.projects.permissions import (
    CanAccessProject,
    IsProjectLeadOrAdmin,
    IsProjectMember,
)
from apps.projects.tests.factories import ProjectFactory, ProjectTeamMemberFactory
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


@pytest.mark.django_db
@pytest.mark.permissions
class TestIsProjectMember:
    """Test IsProjectMember permission."""

    def test_project_member_has_permission(self):
        """Test project member has permission."""
        user = UserFactory()
        project = ProjectFactory()
        ProjectTeamMemberFactory(project=project, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsProjectMember()
        assert permission.has_object_permission(request, None, project) is True

    def test_workspace_member_has_read_permission(self):
        """Test workspace member has read permission to projects."""
        user = UserFactory()
        workspace = WorkspaceFactory()
        project = ProjectFactory(workspace=workspace)

        WorkspaceMemberFactory(workspace=workspace, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsProjectMember()
        assert permission.has_object_permission(request, None, project) is True

    def test_non_member_no_permission(self):
        """Test non-member has no permission."""
        user = UserFactory()
        project = ProjectFactory()

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsProjectMember()
        assert permission.has_object_permission(request, None, project) is False


@pytest.mark.django_db
@pytest.mark.permissions
class TestIsProjectLeadOrAdmin:
    """Test IsProjectLeadOrAdmin permission."""

    def test_project_lead_has_write_permission(self):
        """Test project lead has write permission."""
        user = UserFactory()
        project = ProjectFactory(lead=user)

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsProjectLeadOrAdmin()
        assert permission.has_object_permission(request, None, project) is True

    def test_project_admin_has_write_permission(self):
        """Test project admin role has write permission."""
        user = UserFactory()
        project = ProjectFactory()
        ProjectTeamMemberFactory(project=project, user=user, role="admin")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsProjectLeadOrAdmin()
        assert permission.has_object_permission(request, None, project) is True

    def test_workspace_admin_has_project_admin_permission(self):
        """Test workspace admin has project admin permission."""
        user = UserFactory()
        workspace = WorkspaceFactory()
        project = ProjectFactory(workspace=workspace)

        WorkspaceMemberFactory(workspace=workspace, user=user, role="admin")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsProjectLeadOrAdmin()
        assert permission.has_object_permission(request, None, project) is True

    def test_org_owner_has_project_admin_permission(self):
        """Test organization owner has project admin permission."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user, role="owner")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsProjectLeadOrAdmin()
        assert permission.has_object_permission(request, None, project) is True

    def test_regular_member_no_write_permission(self):
        """Test regular project member has no write permission."""
        user = UserFactory()
        project = ProjectFactory()
        ProjectTeamMemberFactory(project=project, user=user, role="developer")

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = IsProjectLeadOrAdmin()
        assert permission.has_object_permission(request, None, project) is False

    def test_member_has_read_permission(self):
        """Test project member has read permission."""
        user = UserFactory()
        project = ProjectFactory()
        ProjectTeamMemberFactory(project=project, user=user, role="developer")

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = IsProjectLeadOrAdmin()
        assert permission.has_object_permission(request, None, project) is True


@pytest.mark.django_db
@pytest.mark.permissions
class TestCanAccessProject:
    """Test CanAccessProject permission."""

    def test_project_member_can_access(self):
        """Test project member can access."""
        user = UserFactory()
        project = ProjectFactory()
        ProjectTeamMemberFactory(project=project, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessProject()
        assert permission.has_object_permission(request, None, project) is True

    def test_workspace_member_can_read(self):
        """Test workspace member can read project."""
        user = UserFactory()
        workspace = WorkspaceFactory()
        project = ProjectFactory(workspace=workspace)

        WorkspaceMemberFactory(workspace=workspace, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessProject()
        assert permission.has_object_permission(request, None, project) is True

    def test_workspace_member_cannot_write(self):
        """Test workspace member cannot write without project membership."""
        user = UserFactory()
        workspace = WorkspaceFactory()
        project = ProjectFactory(workspace=workspace)

        WorkspaceMemberFactory(workspace=workspace, user=user)

        factory = APIRequestFactory()
        request = factory.patch("/")
        request.user = user

        permission = CanAccessProject()
        assert permission.has_object_permission(request, None, project) is False

    def test_org_member_can_read_public_workspace_project(self):
        """Test org member can read project in public workspace."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org, visibility="public")
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessProject()
        assert permission.has_object_permission(request, None, project) is True

    def test_org_member_cannot_access_private_workspace_project(self):
        """Test org member cannot access project in private workspace."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org, visibility="private")
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user

        permission = CanAccessProject()
        assert permission.has_object_permission(request, None, project) is False
