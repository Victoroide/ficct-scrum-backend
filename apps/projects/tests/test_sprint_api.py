from datetime import date, timedelta

from django.urls import reverse

import pytest
from rest_framework import status

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)
from apps.projects.models import Sprint
from apps.projects.tests.factories import (
    IssueFactory,
    ProjectFactory,
    ProjectTeamMemberFactory,
    SprintFactory,
    WorkflowStatusFactory,
)
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


@pytest.mark.django_db
class TestSprintAPI:
    def test_create_sprint(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace, lead=user)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user, role="project_manager")

        api_client.force_authenticate(user=user)

        url = reverse("sprint-list")
        data = {
            "project": str(project.id),
            "name": "Sprint 1",
            "goal": "Complete initial features",
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=14)),
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        sprint = Sprint.objects.get(name="Sprint 1")
        assert sprint.project == project
        assert sprint.status == "planning"

    def test_start_sprint(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace, lead=user)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user, role="project_manager")

        sprint = SprintFactory(
            project=project,
            status="planning",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
        )
        IssueFactory(project=project, sprint=sprint, story_points=5)
        IssueFactory(project=project, sprint=sprint, story_points=8)

        api_client.force_authenticate(user=user)

        url = reverse("sprint-start-sprint", kwargs={"pk": sprint.id})
        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_200_OK
        sprint.refresh_from_db()
        assert sprint.status == "active"
        assert sprint.committed_points == 13

    def test_cannot_start_sprint_without_issues(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace, lead=user)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user, role="project_manager")

        sprint = SprintFactory(project=project, status="planning")

        api_client.force_authenticate(user=user)

        url = reverse("sprint-start-sprint", kwargs={"pk": sprint.id})
        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_sprint(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace, lead=user)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user, role="project_manager")

        sprint = SprintFactory(project=project, status="active")
        final_status = WorkflowStatusFactory(project=project, is_final=True)
        in_progress_status = WorkflowStatusFactory(project=project, is_final=False)

        IssueFactory(
            project=project, sprint=sprint, status=final_status, story_points=5
        )
        IssueFactory(
            project=project, sprint=sprint, status=in_progress_status, story_points=8
        )

        api_client.force_authenticate(user=user)

        url = reverse("sprint-complete-sprint", kwargs={"pk": sprint.id})
        data = {"move_incomplete_to_backlog": True}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        sprint.refresh_from_db()
        assert sprint.status == "completed"
        assert sprint.completed_points == 5

    def test_view_sprint_progress(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        sprint = SprintFactory(project=project, status="active")
        final_status = WorkflowStatusFactory(project=project, is_final=True)
        in_progress_status = WorkflowStatusFactory(project=project, is_final=False)

        IssueFactory(
            project=project, sprint=sprint, status=final_status, story_points=5
        )
        IssueFactory(
            project=project, sprint=sprint, status=in_progress_status, story_points=8
        )

        api_client.force_authenticate(user=user)

        url = reverse("sprint-progress", kwargs={"pk": sprint.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_issues"] == 2
        assert response.data["completed_issues"] == 1
        assert response.data["remaining_issues"] == 1

    def test_add_issue_to_sprint(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace, lead=user)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user, role="project_manager")

        sprint = SprintFactory(project=project, status="planning")
        issue = IssueFactory(project=project, sprint=None)

        api_client.force_authenticate(user=user)

        url = reverse("sprint-add-issue", kwargs={"pk": sprint.id})
        data = {"issue_id": str(issue.id)}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        issue.refresh_from_db()
        assert issue.sprint == sprint

    def test_remove_issue_from_sprint(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace, lead=user)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user, role="project_manager")

        sprint = SprintFactory(project=project, status="planning")
        issue = IssueFactory(project=project, sprint=sprint)

        api_client.force_authenticate(user=user)

        url = reverse(
            "sprint-remove-issue", kwargs={"pk": sprint.id, "issue_id": issue.id}
        )
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        issue.refresh_from_db()
        assert issue.sprint is None
