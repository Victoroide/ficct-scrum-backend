from django.urls import reverse

import pytest
from rest_framework import status

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)
from apps.projects.models import Issue
from apps.projects.tests.factories import (
    IssueFactory,
    IssueTypeFactory,
    ProjectFactory,
    ProjectTeamMemberFactory,
    WorkflowStatusFactory,
)
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


@pytest.mark.django_db
class TestIssueAPI:
    def test_create_issue(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        issue_type = IssueTypeFactory(project=project, category="task")
        initial_status = WorkflowStatusFactory(project=project, is_initial=True)

        api_client.force_authenticate(user=user)

        url = reverse("issue-list")
        data = {
            "project": str(project.id),
            "issue_type": str(issue_type.id),
            "title": "Test Issue",
            "description": "Test description",
            "priority": "P2",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        issue = Issue.objects.get(title="Test Issue")
        assert issue.project == project
        assert issue.reporter == user
        assert issue.status == initial_status

    def test_list_issues_as_project_member(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        IssueFactory(project=project)
        IssueFactory(project=project)

        api_client.force_authenticate(user=user)

        url = reverse("issue-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 2

    def test_assign_issue(self, api_client):
        user = UserFactory()
        assignee = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        OrganizationMembershipFactory(organization=org, user=assignee)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=assignee)
        ProjectTeamMemberFactory(project=project, user=user)
        ProjectTeamMemberFactory(project=project, user=assignee)

        issue = IssueFactory(project=project, reporter=user)

        api_client.force_authenticate(user=user)

        url = reverse("issue-assign", kwargs={"pk": issue.id})
        data = {"assignee": str(assignee.id)}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        issue.refresh_from_db()
        assert issue.assignee == assignee

    def test_transition_issue_status(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        initial_status = WorkflowStatusFactory(project=project, is_initial=True)
        new_status = WorkflowStatusFactory(project=project, is_final=False)
        issue = IssueFactory(project=project, reporter=user, status=initial_status)

        from apps.projects.models import WorkflowTransition

        WorkflowTransition.objects.create(
            project=project,
            name="Move to In Progress",
            from_status=initial_status,
            to_status=new_status,
            is_active=True,
        )

        api_client.force_authenticate(user=user)

        url = reverse("issue-transition", kwargs={"pk": issue.id})
        data = {"status": str(new_status.id)}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        issue.refresh_from_db()
        assert issue.status == new_status

    def test_set_issue_priority(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        issue = IssueFactory(project=project, reporter=user, priority="P3")

        api_client.force_authenticate(user=user)

        url = reverse("issue-set-priority", kwargs={"pk": issue.id})
        data = {"priority": "P1"}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        issue.refresh_from_db()
        assert issue.priority == "P1"

    def test_unauthorized_access_to_issues(self, api_client):
        user = UserFactory()
        other_user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=other_user)
        WorkspaceMemberFactory(workspace=workspace, user=other_user)
        ProjectTeamMemberFactory(project=project, user=other_user)

        issue = IssueFactory(project=project)

        api_client.force_authenticate(user=user)

        url = reverse("issue-detail", kwargs={"pk": issue.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
