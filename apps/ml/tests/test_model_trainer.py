"""
Unit tests for ModelTrainer with mocked S3.

Tests model training, evaluation, and S3 integration.
"""

from unittest.mock import MagicMock, patch

import pytest
from moto import mock_s3

from apps.authentication.tests.factories import UserFactory
from apps.ml.models import MLModel
from apps.ml.services.model_trainer import ModelTrainer
from apps.projects.tests.factories import IssueFactory, IssueTypeFactory, ProjectFactory


@pytest.fixture
def s3_mock():
    """Mock S3 for tests."""
    with mock_s3():
        import boto3

        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-ml-models-bucket"
        s3_client.create_bucket(Bucket=bucket_name)
        yield bucket_name


@pytest.mark.django_db
class TestModelTrainer:
    """Test ModelTrainer functionality."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.project = ProjectFactory()
        self.issue_type = IssueTypeFactory(project=self.project)

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_train_effort_prediction_model_insufficient_data(self, mock_s3_service):
        """Test training fails gracefully with insufficient data."""
        trainer = ModelTrainer()

        # Create only a few issues (less than minimum)
        for i in range(10):
            IssueFactory(
                project=self.project,
                issue_type=self.issue_type,
                status__is_final=True,
                actual_hours=8.0,
            )

        result = trainer.train_effort_prediction_model(
            project_id=str(self.project.id),
            user=self.user,
        )

        # Should return None due to insufficient data
        assert result is None

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_train_effort_prediction_model_success(self, mock_s3_service, s3_mock):
        """Test successful model training with sufficient data."""
        # Mock S3 upload
        mock_storage = MagicMock()
        mock_storage.upload_model.return_value = (
            "ml_models/effort_prediction/test/model.joblib",
            "test-etag",
        )
        mock_storage.bucket_name = s3_mock
        mock_s3_service.return_value = mock_storage

        trainer = ModelTrainer()

        # Create sufficient training data
        for i in range(60):
            IssueFactory(
                project=self.project,
                issue_type=self.issue_type,
                title=f"Test issue {i}",
                description=f"Description for issue {i}",
                status__is_final=True,
                actual_hours=float(5 + (i % 10)),
                story_points=i % 8 + 1,
            )

        result = trainer.train_effort_prediction_model(
            project_id=str(self.project.id),
            user=self.user,
        )

        # Verify model was created
        assert result is not None
        assert isinstance(result, MLModel)
        assert result.model_type == "effort_prediction"
        assert result.status == "active"
        assert result.is_active is True
        assert result.training_samples >= 50
        assert result.trained_by == self.user

        # Verify metrics were calculated
        assert result.mae is not None
        assert result.rmse is not None
        assert result.r2_score is not None

        # Verify S3 upload was called
        mock_storage.upload_model.assert_called_once()

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_train_story_points_model(self, mock_s3_service, s3_mock):
        """Test story points model training."""
        mock_storage = MagicMock()
        mock_storage.upload_model.return_value = (
            "ml_models/story_points/test/model.joblib",
            "test-etag",
        )
        mock_storage.bucket_name = s3_mock
        mock_s3_service.return_value = mock_storage

        trainer = ModelTrainer()

        # Create training data with story points
        for i in range(60):
            IssueFactory(
                project=self.project,
                issue_type=self.issue_type,
                title=f"Story {i}",
                status__is_final=True,
                story_points=i % 8 + 1,
            )

        result = trainer.train_story_points_model(
            project_id=str(self.project.id),
            user=self.user,
        )

        assert result is not None
        assert result.model_type == "story_points"
        assert result.training_samples >= 50

    def test_fetch_effort_training_data(self):
        """Test fetching training data for effort prediction."""
        trainer = ModelTrainer()

        # Create completed issues with actual hours
        for i in range(20):
            IssueFactory(
                project=self.project,
                issue_type=self.issue_type,
                status__is_final=True,
                actual_hours=float(i + 1),
            )

        # Create issues without actual hours (should be excluded)
        IssueFactory(
            project=self.project,
            status__is_final=True,
            actual_hours=None,
        )

        training_data = trainer._fetch_effort_training_data(str(self.project.id))

        # Verify correct data was fetched
        assert len(training_data) == 20
        assert all("actual_hours" in item for item in training_data)
        assert all(item["actual_hours"] > 0 for item in training_data)

    def test_prepare_effort_features(self):
        """Test feature extraction from training data."""
        trainer = ModelTrainer()

        training_data = [
            {
                "title": "Fix authentication bug",
                "description": "Users cannot login to the system",
                "issue_type": "bug",
                "actual_hours": 8.0,
                "story_points": 5,
                "priority": "P1",
            },
            {
                "title": "Implement user profile",
                "description": "Add user profile page with settings",
                "issue_type": "story",
                "actual_hours": 12.0,
                "story_points": 8,
                "priority": "P2",
            },
        ]

        X, y, feature_names = trainer._prepare_effort_features(training_data)

        # Verify shapes
        assert X.shape[0] == 2  # 2 samples
        assert X.shape[1] == 8  # 8 features
        assert y.shape[0] == 2  # 2 labels
        assert len(feature_names) == 8

        # Verify feature names
        assert "title_length" in feature_names
        assert "is_bug" in feature_names
        assert "is_story" in feature_names
        assert "priority_score" in feature_names

        # Verify feature values
        assert X[0][3] == 1  # is_bug for first issue
        assert X[1][4] == 1  # is_story for second issue

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_should_retrain_old_model(self, mock_s3_service):
        """Test retraining recommendation for old model."""
        from datetime import timedelta

        from django.utils import timezone

        trainer = ModelTrainer()

        # Create old model
        old_model = MLModel.objects.create(
            name="Old Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            training_samples=100,
            training_date=timezone.now() - timedelta(days=35),
        )

        # Should recommend retraining
        assert trainer.should_retrain(old_model) is True

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_should_not_retrain_recent_model(self, mock_s3_service):
        """Test no retraining needed for recent model."""
        trainer = ModelTrainer()

        # Create recent model
        recent_model = MLModel.objects.create(
            name="Recent Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            training_samples=100,
        )

        # Should not recommend retraining
        assert trainer.should_retrain(recent_model) is False

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_serialize_model(self, mock_s3_service):
        """Test model serialization."""
        trainer = ModelTrainer()

        model_bundle = {
            "model": "test_model_object",
            "feature_names": ["feature1", "feature2"],
            "trained_at": "2024-01-01T00:00:00",
        }

        model_bytes = trainer._serialize_model(model_bundle)

        # Verify serialization
        assert isinstance(model_bytes, bytes)
        assert len(model_bytes) > 0

        # Verify can deserialize
        import joblib

        deserialized = joblib.loads(model_bytes)
        assert deserialized["model"] == "test_model_object"
        assert deserialized["feature_names"] == ["feature1", "feature2"]


@pytest.mark.django_db
class TestModelEvaluation:
    """Test model evaluation functionality."""

    def setup_method(self):
        """Set up test data."""
        self.project = ProjectFactory()
        self.issue_type = IssueTypeFactory(project=self.project)

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_evaluate_model_insufficient_data(self, mock_s3_service):
        """Test evaluation with insufficient test data."""
        mock_storage = MagicMock()
        mock_s3_service.return_value = mock_storage

        trainer = ModelTrainer()

        # Create model
        ml_model = MLModel.objects.create(
            name="Test Model",
            model_type="effort_prediction",
            version="1.0.0",
            s3_key="test/key",
            metadata={"project_id": str(self.project.id)},
        )

        # Create minimal test data
        for i in range(5):
            IssueFactory(
                project=self.project,
                issue_type=self.issue_type,
                status__is_final=True,
                actual_hours=8.0,
            )

        # Mock model download
        import joblib

        mock_model_bundle = {
            "model": MagicMock(predict=lambda x: [8.0] * len(x)),
            "feature_names": ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8"],
        }
        mock_storage.download_model.return_value = joblib.dumps(mock_model_bundle)

        metrics = trainer.evaluate_model(str(ml_model.id))

        # Should return default metrics due to insufficient data
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "r2" in metrics


@pytest.mark.django_db
class TestModelTrainerEdgeCases:
    """Test edge cases and error handling."""

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_train_with_no_issues(self, mock_s3_service):
        """Test training with no issues in project."""
        project = ProjectFactory()
        trainer = ModelTrainer()

        result = trainer.train_effort_prediction_model(project_id=str(project.id))

        assert result is None

    @patch("apps.ml.services.model_trainer.S3ModelStorageService")
    def test_train_with_invalid_project_id(self, mock_s3_service):
        """Test training with invalid project ID."""
        trainer = ModelTrainer()

        result = trainer.train_effort_prediction_model(
            project_id="00000000-0000-0000-0000-000000000000"
        )

        assert result is None

    def test_prepare_features_with_empty_descriptions(self):
        """Test feature extraction with missing descriptions."""
        trainer = ModelTrainer()

        training_data = [
            {
                "title": "Test issue",
                "description": "",
                "issue_type": "task",
                "actual_hours": 5.0,
                "story_points": 3,
                "priority": "P2",
            }
        ]

        X, y, feature_names = trainer._prepare_effort_features(training_data)

        assert X.shape[0] == 1
        assert X[0][1] == 0  # description_length should be 0
