"""
Unit tests for ModelLoader with caching and S3 integration.

Tests model loading, caching, and error handling.
"""

from unittest.mock import MagicMock, patch

import joblib
import pytest

from apps.ml.models import MLModel
from apps.ml.services.model_loader import ModelLoader
from apps.ml.tests.factories import MLModelFactory


@pytest.mark.django_db
class TestModelLoader:
    """Test ModelLoader functionality."""

    def setup_method(self):
        """Set up test data."""
        self.loader = ModelLoader()
        # Clear cache before each test
        self.loader.clear_cache()

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_active_model_success(self, mock_s3_service):
        """Test loading active model from S3."""
        # Create active model in database
        ml_model = MLModel.objects.create(
            name="Test Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_bucket="test-bucket",
            s3_key="ml_models/test/model.joblib",
            metadata={"accuracy": 0.85},
        )

        # Mock S3 download
        mock_storage = MagicMock()
        mock_model_bundle = {
            "model": "test_model_object",
            "feature_names": ["f1", "f2", "f3"],
            "trained_at": "2024-01-01",
        }
        mock_storage.download_model.return_value = joblib.dumps(mock_model_bundle)
        mock_s3_service.return_value = mock_storage

        # Load model
        model_data = self.loader.load_active_model(
            model_type="effort_prediction",
            project_id=None,
        )

        # Verify
        assert model_data is not None
        assert model_data["model_id"] == str(ml_model.id)
        assert model_data["version"] == "1.0.0"
        assert model_data["feature_names"] == ["f1", "f2", "f3"]
        assert model_data["ml_model"] == ml_model

        # Verify S3 was called
        mock_storage.download_model.assert_called_once_with(ml_model.s3_key)

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_active_model_with_caching(self, mock_s3_service):
        """Test that loaded models are cached."""
        ml_model = MLModel.objects.create(
            name="Cached Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_key="ml_models/test/model.joblib",
        )

        mock_storage = MagicMock()
        mock_model_bundle = {"model": "test"}
        mock_storage.download_model.return_value = joblib.dumps(mock_model_bundle)
        mock_s3_service.return_value = mock_storage

        # First load - should hit S3
        model_data_1 = self.loader.load_active_model("effort_prediction")
        assert model_data_1 is not None
        assert mock_storage.download_model.call_count == 1

        # Second load - should use cache
        model_data_2 = self.loader.load_active_model("effort_prediction")
        assert model_data_2 is not None
        # S3 should still only be called once (cached)
        assert mock_storage.download_model.call_count == 1

        # Verify both loads return same data
        assert model_data_1["model_id"] == model_data_2["model_id"]

    def test_load_active_model_no_model_found(self):
        """Test loading when no active model exists."""
        model_data = self.loader.load_active_model(
            model_type="nonexistent_type",
            project_id=None,
        )

        assert model_data is None

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_model_project_specific(self, mock_s3_service):
        """Test loading project-specific model."""
        project_id = "test-project-123"

        # Create project-specific model
        ml_model = MLModel.objects.create(
            name="Project Model",
            model_type="effort_prediction",
            version="2.0.0",
            status="active",
            is_active=True,
            s3_key="ml_models/project/model.joblib",
            metadata={"project_id": project_id},
        )

        mock_storage = MagicMock()
        mock_storage.download_model.return_value = joblib.dumps({"model": "test"})
        mock_s3_service.return_value = mock_storage

        # Load project-specific model
        model_data = self.loader.load_active_model(
            model_type="effort_prediction",
            project_id=project_id,
        )

        assert model_data is not None
        assert model_data["model_id"] == str(ml_model.id)

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_model_fallback_to_global(self, mock_s3_service):
        """Test fallback to global model when project-specific not found."""
        project_id = "test-project-456"

        # Create only global model
        ml_model = MLModel.objects.create(
            name="Global Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_key="ml_models/global/model.joblib",
            metadata={},
        )

        mock_storage = MagicMock()
        mock_storage.download_model.return_value = joblib.dumps({"model": "global"})
        mock_s3_service.return_value = mock_storage

        # Try to load project-specific, should fallback to global
        model_data = self.loader.load_active_model(
            model_type="effort_prediction",
            project_id=project_id,
        )

        assert model_data is not None
        assert model_data["model_id"] == str(ml_model.id)

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_model_by_id(self, mock_s3_service):
        """Test loading specific model by ID."""
        ml_model = MLModel.objects.create(
            name="Specific Model",
            model_type="effort_prediction",
            version="1.5.0",
            status="deprecated",
            is_active=False,
            s3_key="ml_models/specific/model.joblib",
        )

        mock_storage = MagicMock()
        mock_storage.download_model.return_value = joblib.dumps({"model": "specific"})
        mock_s3_service.return_value = mock_storage

        # Load by ID
        model_data = self.loader.load_model_by_id(str(ml_model.id))

        assert model_data is not None
        assert model_data["model_id"] == str(ml_model.id)
        assert model_data["version"] == "1.5.0"

    def test_load_model_by_invalid_id(self):
        """Test loading with invalid model ID."""
        with pytest.raises(RuntimeError, match="Model not found"):
            self.loader.load_model_by_id("00000000-0000-0000-0000-000000000000")

    def test_clear_cache(self):
        """Test cache clearing."""
        # Manually add to cache
        self.loader._put_in_cache(
            "test_key",
            {"model": "test_data"},
        )

        # Verify in cache
        cached = self.loader._get_from_cache("test_key")
        assert cached is not None

        # Clear cache
        self.loader.clear_cache()

        # Verify cache cleared
        cached_after = self.loader._get_from_cache("test_key")
        assert cached_after is None

    def test_clear_cache_specific_type(self):
        """Test clearing cache for specific model type."""
        # Add multiple items to cache
        self.loader._put_in_cache("effort_prediction_global", {"model": "effort"})
        self.loader._put_in_cache("story_points_global", {"model": "story"})

        # Clear only effort_prediction
        self.loader.clear_cache(model_type="effort_prediction")

        # Verify only effort_prediction cleared
        assert self.loader._get_from_cache("effort_prediction_global") is None
        assert self.loader._get_from_cache("story_points_global") is not None

    def test_get_cache_stats(self):
        """Test cache statistics."""
        # Add items to cache
        self.loader._put_in_cache("key1", {"data": 1})
        self.loader._put_in_cache("key2", {"data": 2})

        stats = self.loader.get_cache_stats()

        assert stats["total_cached"] == 2
        assert "key1" in stats["cached_keys"]
        assert "key2" in stats["cached_keys"]
        assert "cache_ttl_seconds" in stats

    def test_cache_expiration(self):
        """Test cache entries expire after TTL."""
        from datetime import datetime, timedelta

        # Manually add expired cache entry
        expired_time = datetime.utcnow() - timedelta(hours=2)
        self.loader._model_cache["expired_key"] = {
            "data": {"model": "old"},
            "cached_at": expired_time,
        }

        # Try to get expired entry
        cached = self.loader._get_from_cache("expired_key")

        # Should return None (expired)
        assert cached is None

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_preload_models(self, mock_s3_service):
        """Test preloading models into cache."""
        # Create multiple active models
        MLModel.objects.create(
            name="Effort Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_key="ml_models/effort/model.joblib",
        )
        MLModel.objects.create(
            name="Story Model",
            model_type="story_points",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_key="ml_models/story/model.joblib",
        )

        mock_storage = MagicMock()
        mock_storage.download_model.return_value = joblib.dumps({"model": "test"})
        mock_s3_service.return_value = mock_storage

        # Preload specific types
        results = self.loader.preload_models(["effort_prediction", "story_points"])

        assert results["effort_prediction"] is True
        assert results["story_points"] is True

    def test_build_cache_key(self):
        """Test cache key generation."""
        # Global model key
        key1 = self.loader._build_cache_key("effort_prediction", None)
        assert key1 == "effort_prediction_global"

        # Project-specific key
        key2 = self.loader._build_cache_key("effort_prediction", "project-123")
        assert key2 == "effort_prediction_project_project-123"


@pytest.mark.django_db
class TestModelLoaderErrorHandling:
    """Test error handling in ModelLoader."""

    def setup_method(self):
        """Set up test data."""
        self.loader = ModelLoader()
        self.loader.clear_cache()

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_model_s3_error(self, mock_s3_service):
        """Test handling S3 download errors."""
        ml_model = MLModel.objects.create(
            name="Broken Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_key="ml_models/broken/model.joblib",
        )

        # Mock S3 error
        mock_storage = MagicMock()
        mock_storage.download_model.side_effect = RuntimeError("S3 connection failed")
        mock_s3_service.return_value = mock_storage

        # Should raise error
        with pytest.raises(RuntimeError, match="Failed to load model"):
            self.loader.load_active_model("effort_prediction")

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_model_no_s3_key(self, mock_s3_service):
        """Test loading model without S3 key."""
        ml_model = MLModel.objects.create(
            name="No Key Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_key="",  # Empty S3 key
        )

        mock_s3_service.return_value = MagicMock()

        with pytest.raises(RuntimeError):
            self.loader.load_active_model("effort_prediction")

    @patch("apps.ml.services.model_loader.S3ModelStorageService")
    def test_load_model_corrupt_data(self, mock_s3_service):
        """Test loading corrupt model data."""
        ml_model = MLModel.objects.create(
            name="Corrupt Model",
            model_type="effort_prediction",
            version="1.0.0",
            status="active",
            is_active=True,
            s3_key="ml_models/corrupt/model.joblib",
        )

        mock_storage = MagicMock()
        mock_storage.download_model.return_value = b"corrupt data not joblib"
        mock_s3_service.return_value = mock_storage

        with pytest.raises(RuntimeError):
            self.loader.load_active_model("effort_prediction")
