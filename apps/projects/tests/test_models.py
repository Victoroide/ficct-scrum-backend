"""
Tests for project models.
"""
from django.db import IntegrityError

import pytest

from apps.authentication.tests.factories import UserFactory
from apps.projects.models import Project, ProjectTeamMember, WorkflowStatus
from apps.projects.tests.factories import (
    ProjectFactory,
    ProjectTeamMemberFactory,
    WorkflowStatusFactory,
)
from apps.workspaces.tests.factories import WorkspaceFactory


@pytest.mark.django_db
class TestProjectModel:
    """Test Project model."""

    def test_create_project(self):
        """Test creating a project."""
        project = ProjectFactory(name="Test Project", key="TEST")
        assert project.name == "Test Project"
        assert project.key == "TEST"
        assert project.is_active is True

    def test_project_key_workspace_unique(self):
        """Test project key must be unique within workspace."""
        workspace = WorkspaceFactory()
        ProjectFactory(workspace=workspace, key="TEST")

        with pytest.raises(IntegrityError):
            ProjectFactory(workspace=workspace, key="TEST")

    def test_project_key_different_workspace_allowed(self):
        """Test same key allowed in different workspaces."""
        workspace1 = WorkspaceFactory()
        workspace2 = WorkspaceFactory()

        project1 = ProjectFactory(workspace=workspace1, key="TEST")
        project2 = ProjectFactory(workspace=workspace2, key="TEST")

        assert project1.key == project2.key
        assert project1.workspace != project2.workspace

    def test_project_str(self):
        """Test project string representation."""
        project = ProjectFactory(key="TEST", name="Test Project")
        assert str(project) == "TEST - Test Project"

    def test_project_relationships(self):
        """Test project relationships."""
        workspace = WorkspaceFactory()
        lead = UserFactory()
        creator = UserFactory()

        project = ProjectFactory(workspace=workspace, lead=lead, created_by=creator)

        assert project.workspace == workspace
        assert project.lead == lead
        assert project.created_by == creator


@pytest.mark.django_db
class TestWorkflowStatusModel:
    """Test WorkflowStatus model."""

    def test_create_workflow_status(self):
        """Test creating a workflow status."""
        status = WorkflowStatusFactory(name="To Do", category="to_do")
        assert status.name == "To Do"
        assert status.category == "to_do"

    def test_workflow_status_ordering(self):
        """Test workflow statuses are ordered by order field."""
        project = ProjectFactory()

        status3 = WorkflowStatusFactory(project=project, order=3, name="Done")
        status1 = WorkflowStatusFactory(project=project, order=1, name="To Do")
        status2 = WorkflowStatusFactory(project=project, order=2, name="In Progress")

        statuses = WorkflowStatus.objects.filter(project=project).order_by("order")
        assert list(statuses) == [status1, status2, status3]

    def test_workflow_status_flags(self):
        """Test initial and final flags."""
        project = ProjectFactory()

        initial_status = WorkflowStatusFactory(
            project=project, is_initial=True, is_final=False
        )
        assert initial_status.is_initial is True
        assert initial_status.is_final is False

        final_status = WorkflowStatusFactory(
            project=project, is_initial=False, is_final=True
        )
        assert final_status.is_initial is False
        assert final_status.is_final is True

    def test_workflow_status_str(self):
        """Test workflow status string representation."""
        project = ProjectFactory(key="TEST")
        status = WorkflowStatusFactory(project=project, name="In Progress")
        assert str(status) == "TEST - In Progress"


@pytest.mark.django_db
class TestProjectTeamMemberModel:
    """Test ProjectTeamMember model."""

    def test_create_team_member(self):
        """Test creating a team member."""
        member = ProjectTeamMemberFactory(role="developer")
        assert member.role == "developer"
        assert member.is_active is True

    def test_team_member_str(self):
        """Test team member string representation."""
        user = UserFactory(email="dev@example.com")
        project = ProjectFactory(name="Test Project")
        member = ProjectTeamMemberFactory(user=user, project=project)
        assert "dev@example.com" in str(member)
        assert "Test Project" in str(member)

    def test_unique_together_constraint(self):
        """Test user can only have one membership per project."""
        user = UserFactory()
        project = ProjectFactory()
        ProjectTeamMemberFactory(user=user, project=project)

        with pytest.raises(IntegrityError):
            ProjectTeamMemberFactory(user=user, project=project)
