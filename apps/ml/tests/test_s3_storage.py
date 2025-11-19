"""
Unit tests for S3ModelStorageService with moto mocking.

All S3 operations are mocked - no real AWS calls.
"""

import io
from unittest.mock import patch

import pytest
from moto import mock_s3

from apps.ml.services.s3_model_storage import S3ModelStorageService


@pytest.fixture
def s3_setup():
    """Set up mocked S3 bucket."""
    with mock_s3():
        import boto3

        # Create mock S3 bucket
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-ml-models-bucket"
        s3_client.create_bucket(Bucket=bucket_name)

        yield {
            "bucket_name": bucket_name,
            "s3_client": s3_client,
        }


@pytest.mark.django_db
class TestS3ModelStorageService:
    """Test S3ModelStorageService with mocked S3."""

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_upload_model(self, mock_settings, s3_setup):
        """Test model upload to S3."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Test data
        model_data = b"test model data"
        model_type = "effort_prediction"
        version = "1.0.0"
        metadata = {"accuracy": 0.85, "samples": 100}

        # Upload model
        s3_key, etag = service.upload_model(
            model_data=model_data,
            model_type=model_type,
            version=version,
            metadata=metadata,
        )

        # Verify upload
        assert s3_key.startswith(f"ml_models/{model_type}/{version}/")
        assert s3_key.endswith("/model.joblib")
        assert etag is not None
        assert len(etag) > 0

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_download_model(self, mock_settings, s3_setup):
        """Test model download from S3."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Upload first
        model_data = b"test model content"
        s3_key, _ = service.upload_model(
            model_data=model_data,
            model_type="effort_prediction",
            version="1.0.0",
        )

        # Download
        downloaded_data = service.download_model(s3_key)

        # Verify
        assert downloaded_data == model_data

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_download_nonexistent_model(self, mock_settings, s3_setup):
        """Test downloading non-existent model raises error."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Try to download non-existent model
        with pytest.raises(RuntimeError, match="Model not found"):
            service.download_model("ml_models/nonexistent/1.0.0/model.joblib")

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_upload_dataset(self, mock_settings, s3_setup):
        """Test dataset upload to S3."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Test data
        dataset_data = b"test dataset data"
        dataset_name = "training_set"
        project_id = "test-project-123"

        # Upload
        s3_key = service.upload_dataset(
            dataset_data=dataset_data,
            dataset_name=dataset_name,
            project_id=project_id,
        )

        # Verify
        assert s3_key.startswith(f"ml_datasets/{project_id}/{dataset_name}_")
        assert s3_key.endswith(".pkl")

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_list_models(self, mock_settings, s3_setup):
        """Test listing models in S3."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Upload multiple models
        for i in range(3):
            service.upload_model(
                model_data=f"model {i}".encode(),
                model_type="effort_prediction",
                version=f"1.0.{i}",
            )

        # List models
        models = service.list_models(model_type="effort_prediction")

        # Verify
        assert len(models) == 3
        assert all("key" in model for model in models)
        assert all("size" in model for model in models)

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_delete_model(self, mock_settings, s3_setup):
        """Test model deletion from S3."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Upload model
        s3_key, _ = service.upload_model(
            model_data=b"test model",
            model_type="effort_prediction",
            version="1.0.0",
        )

        # Verify it exists
        assert service.model_exists(s3_key)

        # Delete
        service.delete_model(s3_key)

        # Verify deletion
        assert not service.model_exists(s3_key)

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_model_exists(self, mock_settings, s3_setup):
        """Test checking if model exists in S3."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Check non-existent model
        assert not service.model_exists("ml_models/fake/1.0.0/model.joblib")

        # Upload model
        s3_key, _ = service.upload_model(
            model_data=b"test",
            model_type="effort_prediction",
            version="1.0.0",
        )

        # Check existing model
        assert service.model_exists(s3_key)

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_get_model_metadata(self, mock_settings, s3_setup):
        """Test retrieving model metadata without downloading."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Upload model with metadata
        model_data = b"test model with metadata"
        s3_key, _ = service.upload_model(
            model_data=model_data,
            model_type="effort_prediction",
            version="1.0.0",
            metadata={"accuracy": 0.9},
        )

        # Get metadata
        metadata = service.get_model_metadata(s3_key)

        # Verify
        assert metadata["size"] == len(model_data)
        assert "last_modified" in metadata
        assert "etag" in metadata
        assert "metadata" in metadata

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_upload_without_bucket_configured(self, mock_settings):
        """Test upload fails gracefully when bucket not configured."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = None

        service = S3ModelStorageService()

        with pytest.raises(RuntimeError, match="AWS_STORAGE_BUCKET_NAME not configured"):
            service.upload_model(
                model_data=b"test",
                model_type="effort_prediction",
                version="1.0.0",
            )


@pytest.mark.django_db
class TestS3ErrorHandling:
    """Test error handling in S3 operations."""

    @patch("apps.ml.services.s3_model_storage.settings")
    def test_download_with_network_error(self, mock_settings, s3_setup):
        """Test handling of network errors during download."""
        mock_settings.AWS_STORAGE_BUCKET_NAME = s3_setup["bucket_name"]
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"

        service = S3ModelStorageService()

        # Try to download from non-existent key
        with pytest.raises(RuntimeError):
            service.download_model("invalid/key/path.joblib")
