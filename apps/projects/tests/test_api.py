"""
Tests for project API endpoints.
"""
from django.urls import reverse

import pytest
from rest_framework import status

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)
from apps.projects.models import Project, WorkflowStatus
from apps.projects.tests.factories import ProjectFactory, ProjectTeamMemberFactory
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


@pytest.mark.django_db
class TestProjectAPI:
    """Test Project CRUD endpoints."""

    def test_create_project_with_default_workflows(self, api_client):
        """Test creating project auto-creates 3 workflow statuses."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        # User must be org and workspace member
        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)

        api_client.force_authenticate(user=user)

        url = reverse("project-list")
        data = {
            "workspace": str(workspace.id),
            "name": "Test Project",
            "key": "TEST",
            "description": "Test description",
            "methodology": "scrum",
            "status": "planning",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Verify project created
        project = Project.objects.get(key="TEST")
        assert project.name == "Test Project"

        # Verify 3 workflow statuses created
        workflow_statuses = WorkflowStatus.objects.filter(project=project)
        assert workflow_statuses.count() == 3

        # Verify status names
        status_names = [ws.name for ws in workflow_statuses]
        assert "To Do" in status_names
        assert "In Progress" in status_names
        assert "Done" in status_names

        # Verify initial and final flags
        assert workflow_statuses.filter(is_initial=True).count() == 1
        assert workflow_statuses.filter(is_final=True).count() == 1

        # Verify creator is lead
        assert project.lead == user
        assert project.created_by == user

    def test_list_projects_as_workspace_member(self, api_client):
        """Test listing projects as workspace member."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)

        # Create projects
        project1 = ProjectFactory(workspace=workspace)
        project2 = ProjectFactory(workspace=workspace)

        api_client.force_authenticate(user=user)

        url = reverse("project-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_retrieve_project_as_member(self, api_client):
        """Test retrieving project as workspace member."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)

        project = ProjectFactory(workspace=workspace)

        api_client.force_authenticate(user=user)

        url = reverse("project-detail", args=[project.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(project.id)

    def test_update_project_as_lead(self, api_client):
        """Test updating project as project lead."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)

        project = ProjectFactory(workspace=workspace, lead=user)

        api_client.force_authenticate(user=user)

        url = reverse("project-detail", args=[project.id])
        data = {"name": "Updated Project Name"}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Project Name"

    def test_update_project_as_member_fails(self, api_client):
        """Test updating project as regular member fails."""
        user = UserFactory()
        lead = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)

        project = ProjectFactory(workspace=workspace, lead=lead)

        api_client.force_authenticate(user=user)

        url = reverse("project-detail", args=[project.id])
        data = {"name": "Updated Project Name"}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_project_as_lead(self, api_client):
        """Test deleting project as lead."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user, role="admin")

        project = ProjectFactory(workspace=workspace, lead=user)

        api_client.force_authenticate(user=user)

        url = reverse("project-detail", args=[project.id])
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_access_project_as_non_member_fails(self, api_client):
        """Test accessing project as non-workspace-member fails."""
        user = UserFactory()
        project = ProjectFactory()

        api_client.force_authenticate(user=user)

        url = reverse("project-detail", args=[project.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProjectKeyUniqueness:
    """Test project key uniqueness within workspace."""

    def test_duplicate_key_same_workspace_fails(self, api_client):
        """Test duplicate project key in same workspace fails."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)

        # Create first project
        ProjectFactory(workspace=workspace, key="TEST")

        api_client.force_authenticate(user=user)

        # Try to create second project with same key
        url = reverse("project-list")
        data = {
            "workspace": str(workspace.id),
            "name": "Another Project",
            "key": "TEST",
            "methodology": "scrum",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_same_key_different_workspace_allowed(self, api_client):
        """Test same key in different workspaces is allowed."""
        user = UserFactory()
        org = OrganizationFactory()
        workspace1 = WorkspaceFactory(organization=org)
        workspace2 = WorkspaceFactory(organization=org)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace1, user=user)
        WorkspaceMemberFactory(workspace=workspace2, user=user)

        # Create project in first workspace
        ProjectFactory(workspace=workspace1, key="TEST")

        api_client.force_authenticate(user=user)

        # Create project with same key in second workspace
        url = reverse("project-list")
        data = {
            "workspace": str(workspace2.id),
            "name": "Another Project",
            "key": "TEST",
            "methodology": "scrum",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
