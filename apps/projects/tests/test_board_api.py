import pytest
from django.urls import reverse
from rest_framework import status

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
)
from apps.projects.models import Board, BoardColumn
from apps.projects.tests.factories import (
    BoardColumnFactory,
    BoardFactory,
    IssueFactory,
    ProjectFactory,
    ProjectTeamMemberFactory,
    WorkflowStatusFactory,
)
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


@pytest.mark.django_db
class TestBoardAPI:
    def test_create_board(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        api_client.force_authenticate(user=user)

        url = reverse("board-list")
        data = {
            "project": str(project.id),
            "name": "Main Board",
            "description": "Project main board",
            "board_type": "kanban",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        board = Board.objects.get(name="Main Board")
        assert board.project == project
        assert board.created_by == user

    def test_list_boards(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        BoardFactory(project=project)
        BoardFactory(project=project)

        api_client.force_authenticate(user=user)

        url = reverse("board-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 2

    def test_add_column_to_board(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        board = BoardFactory(project=project, created_by=user)
        workflow_status = WorkflowStatusFactory(project=project)

        api_client.force_authenticate(user=user)

        url = reverse("board-add-column", kwargs={"pk": board.id})
        data = {
            "name": "To Do",
            "workflow_status_id": str(workflow_status.id),
            "order": 1,
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert BoardColumn.objects.filter(board=board).count() == 1

    def test_update_column(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        board = BoardFactory(project=project, created_by=user)
        column = BoardColumnFactory(board=board)

        api_client.force_authenticate(user=user)

        url = reverse("board-update-column", kwargs={"pk": board.id, "column_id": column.id})
        data = {
            "name": "Updated Column",
            "max_wip": 5,
        }
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        column.refresh_from_db()
        assert column.name == "Updated Column"
        assert column.max_wip == 5

    def test_delete_column(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        board = BoardFactory(project=project, created_by=user)
        column = BoardColumnFactory(board=board)

        api_client.force_authenticate(user=user)

        url = reverse("board-delete-column", kwargs={"pk": board.id, "column_id": column.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not BoardColumn.objects.filter(id=column.id).exists()

    def test_create_issue_from_board(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        from apps.projects.tests.factories import IssueTypeFactory, WorkflowStatusFactory
        board = BoardFactory(project=project)
        issue_type = IssueTypeFactory(project=project)
        WorkflowStatusFactory(project=project, is_initial=True)

        api_client.force_authenticate(user=user)

        url = reverse("board-create-issue", kwargs={"pk": board.id})
        data = {
            "issue_type": str(issue_type.id),
            "title": "New Issue from Board",
            "description": "Created from board",
            "priority": "P2",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Issue from Board"

    def test_move_issue_in_board(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        board = BoardFactory(project=project)
        status1 = WorkflowStatusFactory(project=project)
        status2 = WorkflowStatusFactory(project=project)
        column1 = BoardColumnFactory(board=board, workflow_status=status1)
        column2 = BoardColumnFactory(board=board, workflow_status=status2)
        issue = IssueFactory(project=project, status=status1)

        api_client.force_authenticate(user=user)

        url = reverse("board-move-issue", kwargs={"pk": board.id, "issue_id": issue.id})
        data = {"column_id": str(column2.id)}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        issue.refresh_from_db()
        assert issue.status == status2

    def test_move_issue_respects_wip_limit(self, api_client):
        user = UserFactory()
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(workspace=workspace)

        OrganizationMembershipFactory(organization=org, user=user)
        WorkspaceMemberFactory(workspace=workspace, user=user)
        ProjectTeamMemberFactory(project=project, user=user)

        board = BoardFactory(project=project)
        status1 = WorkflowStatusFactory(project=project)
        status2 = WorkflowStatusFactory(project=project)
        column1 = BoardColumnFactory(board=board, workflow_status=status1)
        column2 = BoardColumnFactory(board=board, workflow_status=status2, max_wip=1)

        IssueFactory(project=project, status=status2)
        issue_to_move = IssueFactory(project=project, status=status1)

        api_client.force_authenticate(user=user)

        url = reverse("board-move-issue", kwargs={"pk": board.id, "issue_id": issue_to_move.id})
        data = {"column_id": str(column2.id)}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "WIP limit" in response.data["error"]
