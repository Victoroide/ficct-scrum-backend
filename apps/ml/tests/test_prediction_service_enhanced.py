"""
Unit tests for enhanced PredictionService with ML model integration.

Tests all prediction methods with ML model fallbacks.
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.ml.models import PredictionHistory
from apps.ml.services.prediction_service import PredictionService
from apps.ml.tests.factories import MLModelFactory
from apps.projects.tests.factories import (
    IssueFactory,
    IssueTypeFactory,
    ProjectFactory,
    SprintFactory,
)


@pytest.mark.django_db
class TestPredictionServiceWithMLModel:
    """Test PredictionService with ML model integration."""

    def setup_method(self):
        """Set up test data."""
        self.service = PredictionService()
        self.project = ProjectFactory()
        self.issue_type = IssueTypeFactory(project=self.project)

    @patch("apps.ml.services.prediction_service.ModelLoader")
    def test_predict_effort_with_ml_model(self, mock_loader):
        """Test effort prediction using ML model."""
        # Mock ML model
        mock_model = MagicMock()
        mock_model.predict.return_value = [10.5]

        mock_ml_model = MLModelFactory.build(
            model_type="effort_prediction",
            version="1.0.0",
            r2_score=0.85,
        )

        mock_model_data = {
            "model": mock_model,
            "model_id": str(mock_ml_model.id),
            "version": "1.0.0",
            "ml_model": mock_ml_model,
            "feature_names": ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8"],
        }

        mock_loader_instance = MagicMock()
        mock_loader_instance.load_active_model.return_value = mock_model_data
        mock_loader.return_value = mock_loader_instance

        result = self.service.predict_issue_effort(
            title="Fix authentication bug",
            description="Users cannot login",
            issue_type="bug",
            project_id=str(self.project.id),
        )

        # Verify ML model was used
        assert result["method"] == "ml_model"
        assert result["predicted_hours"] > 0
        assert "confidence" in result
        assert "model_version" in result

    @patch("apps.ml.services.prediction_service.ModelLoader")
    def test_predict_effort_ml_fallback_to_similarity(self, mock_loader):
        """Test fallback to similarity when ML model unavailable."""
        # Mock no ML model available
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_active_model.return_value = None
        mock_loader.return_value = mock_loader_instance

        # Create similar completed issues
        for i in range(5):
            IssueFactory(
                project=self.project,
                issue_type=self.issue_type,
                title="Fix login bug",
                status__is_final=True,
                actual_hours=8.0,
            )

        result = self.service.predict_issue_effort(
            title="Fix authentication bug",
            description="Users cannot login",
            issue_type="bug",
            project_id=str(self.project.id),
        )

        # Should use similarity method
        assert result["method"] == "similarity"
        assert result["predicted_hours"] > 0

    def test_predict_effort_heuristic_fallback(self):
        """Test fallback to heuristic when no data available."""
        result = self.service.predict_issue_effort(
            title="New feature",
            description="Implement something new",
            issue_type="feature",
            project_id=str(self.project.id),
        )

        # Should use heuristic
        assert result["method"] == "heuristic"
        assert result["predicted_hours"] > 0
        assert result["confidence"] < 0.5

    def test_extract_features_for_model(self):
        """Test feature extraction for ML model."""
        feature_names = [
            "title_length",
            "description_length",
            "text_length",
            "is_bug",
            "is_story",
            "is_task",
            "priority_score",
            "story_points",
        ]

        features = self.service._extract_features_for_model(
            title="Fix authentication bug",
            description="Users cannot login to the system",
            issue_type="bug",
            feature_names=feature_names,
        )

        # Verify feature vector
        assert len(features) == 8
        assert features[0] == 3  # title_length
        assert features[1] == 6  # description_length
        assert features[3] == 1  # is_bug
        assert features[4] == 0  # is_story

    @patch("apps.ml.services.prediction_service.ModelLoader")
    def test_store_prediction_history(self, mock_loader):
        """Test prediction history is stored."""
        ml_model = MLModelFactory()

        self.service._store_prediction_history(
            model_id=str(ml_model.id),
            input_data={"title": "Test", "issue_type": "task"},
            predicted_value=8.5,
            confidence=0.75,
            project_id=str(self.project.id),
        )

        # Verify history was created
        history = PredictionHistory.objects.filter(model=ml_model)
        assert history.count() == 1
        assert history.first().predicted_value == 8.5

    def test_find_similar_completed_issues(self):
        """Test finding similar completed issues."""
        # Create completed issues with varying similarity
        IssueFactory(
            project=self.project,
            title="Fix authentication bug in login",
            status__is_final=True,
            actual_hours=8.0,
        )
        IssueFactory(
            project=self.project,
            title="Fix password reset feature",
            status__is_final=True,
            actual_hours=6.0,
        )
        IssueFactory(
            project=self.project,
            title="Implement new dashboard",
            status__is_final=True,
            actual_hours=20.0,
        )

        similar = self.service._find_similar_completed_issues(
            title="Fix authentication bug",
            description="Bug in login system",
            project_id=str(self.project.id),
            limit=5,
        )

        # Verify results
        assert len(similar) > 0
        # Most similar should be first
        assert (
            "authentication" in similar[0]["title"].lower()
            or "login" in similar[0]["title"].lower()
        )

    def test_get_average_effort_by_type(self):
        """Test getting average effort by issue type."""
        # Create issues of specific type
        for i in range(5):
            IssueFactory(
                project=self.project,
                issue_type=self.issue_type,
                status__is_final=True,
                actual_hours=float(10 + i),
            )

        avg = self.service._get_average_effort_by_type(
            str(self.project.id),
            self.issue_type.name,
        )

        # Should be around 12 (10+11+12+13+14)/5
        assert avg == pytest.approx(12.0, rel=0.1)


@pytest.mark.django_db
class TestSprintDurationPrediction:
    """Test sprint duration prediction methods."""

    def setup_method(self):
        """Set up test data."""
        self.service = PredictionService()
        self.project = ProjectFactory()

    def test_predict_sprint_duration_from_dates(self):
        """Test prediction using sprint dates."""
        from datetime import date, timedelta

        sprint = SprintFactory(
            project=self.project,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
        )

        result = self.service.predict_sprint_duration(
            sprint_id=str(sprint.id),
            planned_issues=[],
            team_capacity_hours=160,
        )

        assert result["method"] == "from_sprint_dates"
        assert result["estimated_days"] == 14
        assert result["confidence"] >= 0.9

    def test_predict_sprint_duration_from_hours(self):
        """Test prediction using estimated hours."""
        sprint = SprintFactory(project=self.project)

        # Add issues with estimated hours
        for i in range(5):
            IssueFactory(
                project=self.project,
                sprint=sprint,
                estimated_hours=8.0,
            )

        result = self.service.predict_sprint_duration(
            sprint_id=str(sprint.id),
            planned_issues=[],
            team_capacity_hours=160,
        )

        assert result["method"] == "from_estimated_hours"
        assert result["estimated_days"] == 5  # 40 hours / 8 hours per day

    def test_predict_sprint_duration_from_velocity(self):
        """Test prediction using historical velocity."""
        from datetime import date, timedelta

        # Create completed sprint with velocity
        past_sprint = SprintFactory(
            project=self.project,
            status="completed",
            start_date=date.today() - timedelta(days=28),
            completed_at=date.today() - timedelta(days=14),
            completed_points=20,
        )

        # Add completed issues to past sprint
        for i in range(4):
            IssueFactory(
                project=self.project,
                sprint=past_sprint,
                story_points=5,
                status__is_final=True,
            )

        # Create new sprint
        new_sprint = SprintFactory(project=self.project)
        for i in range(3):
            IssueFactory(
                project=self.project,
                sprint=new_sprint,
                story_points=5,
            )

        result = self.service.predict_sprint_duration(
            sprint_id=str(new_sprint.id),
            planned_issues=[],
            team_capacity_hours=160,
        )

        assert result["method"] == "velocity_based"
        assert result["estimated_days"] > 0

    def test_predict_sprint_duration_default(self):
        """Test default fallback when no data available."""
        sprint = SprintFactory(project=self.project)

        result = self.service.predict_sprint_duration(
            sprint_id=str(sprint.id),
            planned_issues=[],
            team_capacity_hours=0,
        )

        assert result["method"] == "default"
        assert result["estimated_days"] == 14
        assert result["confidence"] == 0.0

    def test_predict_sprint_duration_nonexistent_sprint(self):
        """Test handling of non-existent sprint."""
        result = self.service.predict_sprint_duration(
            sprint_id="00000000-0000-0000-0000-000000000000",
            planned_issues=[],
            team_capacity_hours=160,
        )

        assert result["method"] == "default"
        assert "error" in result


@pytest.mark.django_db
class TestStoryPointsRecommendation:
    """Test story points recommendation."""

    def setup_method(self):
        """Set up test data."""
        self.service = PredictionService()
        self.project = ProjectFactory()

    def test_recommend_story_points_with_similar_issues(self):
        """Test recommendation based on similar issues."""
        # Create similar completed issues
        for i in range(10):
            IssueFactory(
                project=self.project,
                title="Implement user feature",
                status__is_final=True,
                story_points=5,
            )

        result = self.service.recommend_story_points(
            title="Implement profile feature",
            description="Add user profile",
            issue_type="story",
            project_id=str(self.project.id),
        )

        assert result["method"] == "similarity"
        assert result["recommended_points"] == 5
        assert result["confidence"] > 0.5

    def test_recommend_story_points_heuristic(self):
        """Test heuristic recommendation when no similar issues."""
        result = self.service.recommend_story_points(
            title="New feature",
            description="Something completely new",
            issue_type="story",
            project_id=str(self.project.id),
        )

        assert result["method"] == "heuristic"
        assert result["recommended_points"] in [1, 2, 3, 5, 8, 13]

    def test_recommend_story_points_distribution(self):
        """Test probability distribution calculation."""
        # Create issues with varying story points
        for points in [3, 3, 5, 5, 5, 8]:
            IssueFactory(
                project=self.project,
                title="Feature implementation",
                status__is_final=True,
                story_points=points,
            )

        result = self.service.recommend_story_points(
            title="Feature implementation",
            description="Similar feature",
            issue_type="story",
            project_id=str(self.project.id),
        )

        assert "probability_distribution" in result
        # 5 points should have highest probability (3/6)
        assert result["recommended_points"] == 5


@pytest.mark.django_db
class TestPredictionServiceErrorHandling:
    """Test error handling in prediction service."""

    def setup_method(self):
        """Set up test data."""
        self.service = PredictionService()
        self.project = ProjectFactory()

    def test_predict_effort_with_exception(self):
        """Test graceful error handling in prediction."""
        with patch.object(
            self.service,
            "_predict_with_similarity",
            side_effect=Exception("Unexpected error"),
        ):
            result = self.service.predict_issue_effort(
                title="Test",
                description="Test",
                issue_type="task",
                project_id=str(self.project.id),
            )

            # Should return default with error
            assert result["method"] == "default"
            assert "error" in result

    def test_recommend_story_points_with_exception(self):
        """Test error handling in story points recommendation."""
        with patch.object(
            self.service,
            "_find_similar_completed_issues",
            side_effect=Exception("Database error"),
        ):
            result = self.service.recommend_story_points(
                title="Test",
                description="Test",
                issue_type="task",
                project_id=str(self.project.id),
            )

            # Should return default
            assert result["recommended_points"] > 0
            assert "error" in result

    def test_predict_with_empty_input(self):
        """Test prediction with empty inputs."""
        result = self.service.predict_issue_effort(
            title="",
            description="",
            issue_type="task",
            project_id=str(self.project.id),
        )

        # Should still return a prediction
        assert result["predicted_hours"] > 0
        assert result["method"] in ["heuristic", "default"]
