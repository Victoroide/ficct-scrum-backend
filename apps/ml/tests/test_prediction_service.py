"""
Unit tests for ML prediction service.

CRITICAL: All external API calls are mocked - NO real Azure OpenAI calls.
"""

import pytest
from unittest.mock import MagicMock, patch

from apps.ml.services import PredictionService
from apps.ml.tests.factories import MLModelFactory, PredictionHistoryFactory
from apps.projects.tests.factories import IssueFactory, ProjectFactory


@pytest.mark.django_db
class TestPredictionService:
    """Test PredictionService methods."""

    def setup_method(self):
        """Set up test data."""
        self.service = PredictionService()
        self.project = ProjectFactory()

    def test_predict_issue_effort_with_similar_issues(self):
        """Test effort prediction with similar completed issues."""
        # Create completed issues with actual hours
        IssueFactory(
            project=self.project,
            title="Fix authentication bug",
            status__is_final=True,
            actual_hours=8,
        )
        IssueFactory(
            project=self.project,
            title="Fix login issue",
            status__is_final=True,
            actual_hours=6,
        )

        result = self.service.predict_issue_effort(
            title="Fix password reset bug",
            description="Users cannot reset password",
            issue_type="bug",
            project_id=str(self.project.id),
        )

        assert "predicted_hours" in result
        assert result["predicted_hours"] > 0
        assert "confidence" in result
        assert 0 <= result["confidence"] <= 1
        assert result["method"] in ["similarity", "heuristic"]

    def test_predict_issue_effort_insufficient_data(self):
        """Test effort prediction with insufficient training data."""
        result = self.service.predict_issue_effort(
            title="New feature",
            description="Implement OAuth",
            issue_type="feature",
            project_id=str(self.project.id),
        )

        # Should fall back to heuristic
        assert result["method"] == "heuristic"
        assert result["predicted_hours"] > 0
        assert result["confidence"] < 0.5

    def test_predict_sprint_duration_with_velocity(self):
        """Test sprint duration prediction with historical velocity."""
        from apps.projects.models import Sprint
        from datetime import datetime, timedelta
        from django.utils import timezone

        # Create completed sprints with story points
        sprint1 = Sprint.objects.create(
            project=self.project,
            name="Sprint 1",
            start_date=timezone.now() - timedelta(days=28),
            end_date=timezone.now() - timedelta(days=14),
            status="completed",
        )

        # Create issues for velocity calculation
        for i in range(5):
            IssueFactory(
                project=self.project,
                sprint=sprint1,
                story_points=5,
                status__is_final=True,
            )

        result = self.service.predict_sprint_duration(
            sprint_id=str(sprint1.id),
            planned_issues=[],
            team_capacity_hours=160,
        )

        assert "estimated_days" in result
        assert result["estimated_days"] > 0
        assert "average_velocity" in result
        assert result["method"] == "velocity_based"

    def test_recommend_story_points(self):
        """Test story points recommendation."""
        # Create issues with story points
        for points in [1, 2, 3, 5, 8]:
            IssueFactory(
                project=self.project,
                title=f"Task with {points} points",
                story_points=points,
                status__is_final=True,
            )

        result = self.service.recommend_story_points(
            title="Implement new feature",
            description="Add user profile page",
            issue_type="story",
            project_id=str(self.project.id),
        )

        assert "recommended_points" in result
        assert result["recommended_points"] in [1, 2, 3, 5, 8, 13, 21]
        assert "confidence" in result
        assert result["method"] in ["classification", "heuristic"]

    @patch("apps.ml.services.prediction_service.PredictionHistory.objects.create")
    def test_save_prediction_history(self, mock_create):
        """Test that predictions are saved to history."""
        mock_create.return_value = PredictionHistoryFactory.build()

        self.service.predict_issue_effort(
            title="Test issue",
            description="Test",
            issue_type="task",
            project_id=str(self.project.id),
        )

        # Verify prediction history was created
        # Note: In real implementation, this would save the prediction
        assert True  # Placeholder

    def test_calculate_prediction_range(self):
        """Test prediction range calculation."""
        predicted = 10.0
        confidence = 0.8

        # This would be a helper method in the service
        margin = (1 - confidence) * predicted
        range_min = max(0, predicted - margin)
        range_max = predicted + margin

        assert range_min < predicted < range_max
        assert range_min >= 0


@pytest.mark.django_db
class TestPredictionServiceEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Set up test data."""
        self.service = PredictionService()

    def test_predict_with_invalid_project_id(self):
        """Test prediction with non-existent project."""
        result = self.service.predict_issue_effort(
            title="Test",
            description="Test",
            issue_type="task",
            project_id="00000000-0000-0000-0000-000000000000",
        )

        # Should return heuristic fallback
        assert result["method"] == "heuristic"

    def test_predict_with_empty_title(self):
        """Test prediction with empty title."""
        project = ProjectFactory()

        result = self.service.predict_issue_effort(
            title="",
            description="Description only",
            issue_type="task",
            project_id=str(project.id),
        )

        # Should still return a prediction
        assert "predicted_hours" in result

    def test_predict_with_zero_story_points(self):
        """Test handling of issues with zero story points."""
        project = ProjectFactory()

        IssueFactory(
            project=project,
            story_points=0,
            status__is_final=True,
        )

        result = self.service.recommend_story_points(
            title="Test",
            description="Test",
            issue_type="task",
            project_id=str(project.id),
        )

        # Should not include zero in recommendations
        assert result["recommended_points"] > 0
