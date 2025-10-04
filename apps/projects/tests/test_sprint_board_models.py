import pytest
from datetime import date, timedelta
from django.core.exceptions import ValidationError

from apps.projects.models import Sprint, BoardColumn
from apps.projects.tests.factories import (
    BoardColumnFactory,
    BoardFactory,
    IssueFactory,
    ProjectFactory,
    SprintFactory,
    WorkflowStatusFactory,
)


@pytest.mark.django_db
class TestSprintModel:
    def test_sprint_creation(self):
        sprint = SprintFactory()
        assert sprint.id is not None
        assert sprint.name is not None
        assert sprint.status == "planning"

    def test_sprint_unique_name_per_project(self):
        project = ProjectFactory()
        SprintFactory(project=project, name="Sprint 1")

        with pytest.raises(Exception):
            SprintFactory(project=project, name="Sprint 1")

    def test_sprint_same_name_different_projects(self):
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        sprint1 = SprintFactory(project=project1, name="Sprint 1")
        sprint2 = SprintFactory(project=project2, name="Sprint 1")

        assert sprint1.name == sprint2.name
        assert sprint1.project != sprint2.project

    def test_sprint_is_active_property(self):
        sprint_planning = SprintFactory(status="planning")
        sprint_active = SprintFactory(status="active")
        sprint_completed = SprintFactory(status="completed")

        assert sprint_planning.is_active is False
        assert sprint_active.is_active is True
        assert sprint_completed.is_active is False

    def test_sprint_duration_days(self):
        start = date.today()
        end = start + timedelta(days=14)
        sprint = SprintFactory(start_date=start, end_date=end)

        assert sprint.duration_days == 14

    def test_sprint_progress_percentage(self):
        sprint = SprintFactory(committed_points=100, completed_points=50)
        assert sprint.progress_percentage == 50.0

        sprint_zero = SprintFactory(committed_points=0, completed_points=0)
        assert sprint_zero.progress_percentage == 0

    def test_sprint_issue_count(self):
        sprint = SprintFactory()
        project = sprint.project

        IssueFactory(project=project, sprint=sprint)
        IssueFactory(project=project, sprint=sprint)
        IssueFactory(project=project, sprint=sprint, is_active=False)

        assert sprint.issue_count == 2


@pytest.mark.django_db
class TestBoardModel:
    def test_board_creation(self):
        board = BoardFactory()
        assert board.id is not None
        assert board.name is not None
        assert board.board_type in ["kanban", "scrum"]

    def test_board_column_count(self):
        board = BoardFactory()
        BoardColumnFactory(board=board)
        BoardColumnFactory(board=board)

        assert board.column_count == 2

    def test_board_issue_count(self):
        board = BoardFactory()
        project = board.project

        IssueFactory(project=project)
        IssueFactory(project=project)
        IssueFactory(project=project, is_active=False)

        assert board.issue_count == 2


@pytest.mark.django_db
class TestBoardColumnModel:
    def test_board_column_creation(self):
        column = BoardColumnFactory()
        assert column.id is not None
        assert column.name is not None

    def test_board_column_unique_order_per_board(self):
        board = BoardFactory()
        BoardColumnFactory(board=board, order=1)

        with pytest.raises(Exception):
            BoardColumnFactory(board=board, order=1)

    def test_board_column_validation_workflow_status_project(self):
        board = BoardFactory()
        other_project = ProjectFactory()
        other_status = WorkflowStatusFactory(project=other_project)

        column = BoardColumn(
            board=board,
            workflow_status=other_status,
            name="Test Column",
            order=1
        )

        with pytest.raises(ValidationError):
            column.full_clean()

    def test_board_column_validation_wip_limits(self):
        board = BoardFactory()
        status = WorkflowStatusFactory(project=board.project)

        column = BoardColumn(
            board=board,
            workflow_status=status,
            name="Test Column",
            order=1,
            min_wip=10,
            max_wip=5
        )

        with pytest.raises(ValidationError):
            column.full_clean()

    def test_board_column_issue_count(self):
        board = BoardFactory()
        project = board.project
        status = WorkflowStatusFactory(project=project)
        column = BoardColumnFactory(board=board, workflow_status=status)

        IssueFactory(project=project, status=status)
        IssueFactory(project=project, status=status)
        IssueFactory(project=project, status=status, is_active=False)

        assert column.issue_count == 2
