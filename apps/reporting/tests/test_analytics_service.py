"""
Comprehensive tests for AnalyticsService.
"""

import csv
import io
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.projects.tests.factories import (
    IssueFactory,
    ProjectFactory,
    SprintFactory,
    WorkflowStatusFactory,
)
from apps.reporting.services.analytics_service import AnalyticsService


@pytest.mark.django_db
class TestAnalyticsService:
    """Test analytics service methods."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = AnalyticsService()
        self.project = ProjectFactory()

    def test_generate_velocity_chart_no_sprints(self):
        """Test velocity chart with no sprints."""
        data = self.service.generate_velocity_chart(self.project, num_sprints=5)

        assert data["labels"] == []
        assert data["velocities"] == []
        assert data["average_velocity"] == 0

    def test_generate_velocity_chart_single_sprint(self):
        """Test velocity chart with one completed sprint."""
        # Create completed sprint with issues
        sprint = SprintFactory(project=self.project, status="completed")
        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )

        IssueFactory(
            project=self.project,
            sprint=sprint,
            status=done_status,
            story_points=5,
        )
        IssueFactory(
            project=self.project,
            sprint=sprint,
            status=done_status,
            story_points=8,
        )

        data = self.service.generate_velocity_chart(self.project, num_sprints=5)

        assert len(data["labels"]) == 1
        assert len(data["velocities"]) == 1
        assert data["velocities"][0] == 13
        assert data["average_velocity"] == 13.0

    def test_generate_velocity_chart_multiple_sprints(self):
        """Test velocity chart with multiple completed sprints."""
        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )

        # Create 3 completed sprints
        for i in range(3):
            sprint = SprintFactory(
                project=self.project, status="completed", name=f"Sprint {i+1}"
            )
            # Add varying story points
            IssueFactory(
                project=self.project,
                sprint=sprint,
                status=done_status,
                story_points=(i + 1) * 10,
            )

        data = self.service.generate_velocity_chart(self.project, num_sprints=5)

        assert len(data["labels"]) == 3
        assert data["velocities"] == [10, 20, 30]
        assert data["average_velocity"] == 20.0

    def test_generate_sprint_report_active_sprint(self):
        """Test sprint report for active sprint."""
        sprint = SprintFactory(project=self.project, status="active")
        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )
        todo_status = WorkflowStatusFactory(
            project=self.project, name="To Do", category="todo"
        )

        # Create issues with different statuses
        IssueFactory(
            project=self.project,
            sprint=sprint,
            status=done_status,
            story_points=8,
        )
        IssueFactory(
            project=self.project,
            sprint=sprint,
            status=done_status,
            story_points=5,
        )
        IssueFactory(
            project=self.project,
            sprint=sprint,
            status=todo_status,
            story_points=3,
        )

        report = self.service.generate_sprint_report(sprint)

        assert report["sprint"]["name"] == sprint.name
        assert report["metrics"]["planned_points"] == 16
        assert report["metrics"]["completed_points"] == 13
        assert report["metrics"]["velocity"] == 13
        assert report["issues_by_status"]["done"] == 2
        assert len(report["incomplete_issues"]) == 1

    def test_generate_sprint_report_completed_sprint(self):
        """Test sprint report for completed sprint."""
        sprint = SprintFactory(project=self.project, status="completed")
        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )

        for i in range(5):
            IssueFactory(
                project=self.project,
                sprint=sprint,
                status=done_status,
                story_points=i + 1,
            )

        report = self.service.generate_sprint_report(sprint)

        assert report["metrics"]["planned_points"] == 15
        assert report["metrics"]["completed_points"] == 15
        assert report["metrics"]["completion_rate"] == 100.0
        assert len(report["incomplete_issues"]) == 0

    def test_generate_team_metrics(self):
        """Test team metrics generation."""
        from apps.authentication.tests.factories import UserFactory

        user1 = UserFactory()
        user2 = UserFactory()

        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )

        # Create issues for user1
        for i in range(3):
            IssueFactory(
                project=self.project,
                assignee=user1,
                status=done_status,
                story_points=5,
            )

        # Create issues for user2
        for i in range(2):
            IssueFactory(
                project=self.project,
                assignee=user2,
                status=done_status,
                story_points=8,
            )

        metrics = self.service.generate_team_metrics(self.project)

        assert len(metrics["members"]) == 2
        # Find user1's metrics
        user1_metrics = next(
            m for m in metrics["members"] if m["user"]["id"] == str(user1.id)
        )
        assert user1_metrics["completed_issues"] == 3
        assert user1_metrics["total_story_points"] == 15

    def test_generate_cumulative_flow_diagram(self):
        """Test cumulative flow diagram generation."""
        todo_status = WorkflowStatusFactory(
            project=self.project, name="To Do", category="todo"
        )
        in_progress_status = WorkflowStatusFactory(
            project=self.project, name="In Progress", category="in_progress"
        )
        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )

        # Create issues with different statuses
        IssueFactory(project=self.project, status=todo_status)
        IssueFactory(project=self.project, status=todo_status)
        IssueFactory(project=self.project, status=in_progress_status)
        IssueFactory(project=self.project, status=done_status)
        IssueFactory(project=self.project, status=done_status)
        IssueFactory(project=self.project, status=done_status)

        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()

        data = self.service.generate_cumulative_flow_diagram(
            self.project, start_date, end_date
        )

        assert "dates" in data
        assert "statuses" in data
        assert len(data["statuses"]) == 3

    def test_export_to_csv_issues(self):
        """Test exporting issues to CSV."""
        IssueFactory(project=self.project, title="Issue 1")
        IssueFactory(project=self.project, title="Issue 2")
        IssueFactory(project=self.project, title="Issue 3")

        csv_content = self.service.export_to_csv(
            data_type="issues",
            queryset=self.project.issues.all(),
            columns=["key", "title", "status", "priority"],
        )

        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 3
        assert "key" in rows[0]
        assert "title" in rows[0]

    def test_export_to_csv_sprints(self):
        """Test exporting sprints to CSV."""
        SprintFactory(project=self.project, name="Sprint 1")
        SprintFactory(project=self.project, name="Sprint 2")

        from apps.projects.models import Sprint

        csv_content = self.service.export_to_csv(
            data_type="sprints",
            queryset=Sprint.objects.filter(project=self.project),
            columns=["name", "status", "start_date", "end_date"],
        )

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 2
        assert "name" in rows[0]

    def test_generate_project_dashboard(self):
        """Test project dashboard generation."""
        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )
        todo_status = WorkflowStatusFactory(
            project=self.project, name="To Do", category="todo"
        )

        # Create issues
        IssueFactory(project=self.project, status=done_status)
        IssueFactory(project=self.project, status=done_status)
        IssueFactory(project=self.project, status=done_status)
        IssueFactory(project=self.project, status=todo_status)
        IssueFactory(project=self.project, status=todo_status)

        # Create active sprint
        sprint = SprintFactory(project=self.project, status="active")

        dashboard = self.service.generate_project_dashboard(self.project)

        assert dashboard["summary"]["total_issues"] == 5
        assert dashboard["summary"]["completed_issues"] == 3
        assert dashboard["summary"]["completion_rate"] == 60.0
        assert dashboard["summary"]["active_sprint"]["name"] == sprint.name

    def test_generate_project_dashboard_no_active_sprint(self):
        """Test dashboard when no active sprint exists."""
        IssueFactory(project=self.project)
        IssueFactory(project=self.project)

        dashboard = self.service.generate_project_dashboard(self.project)

        assert dashboard["summary"]["total_issues"] == 2
        assert dashboard["summary"]["active_sprint"] is None

    def test_velocity_chart_limits_sprints(self):
        """Test that velocity chart respects num_sprints limit."""
        done_status = WorkflowStatusFactory(
            project=self.project, name="Done", category="done"
        )

        # Create 10 sprints
        for i in range(10):
            sprint = SprintFactory(
                project=self.project, status="completed", name=f"Sprint {i+1}"
            )
            IssueFactory(
                project=self.project,
                sprint=sprint,
                status=done_status,
                story_points=10,
            )

        # Request only 5
        data = self.service.generate_velocity_chart(self.project, num_sprints=5)

        assert len(data["labels"]) == 5
        assert len(data["velocities"]) == 5
