"""
S3 storage service for ML models.

Handles all S3 operations for model persistence including upload, download,
versioning, and cleanup.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class S3ModelStorageService:
    """Service for storing and retrieving ML models from S3."""

    def __init__(self):
        """Initialize S3 client with configuration."""
        self.bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
        self.region = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")

        # S3 configuration with retry logic
        config = Config(
            region_name=self.region,
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=30,
        )

        # Initialize S3 client
        aws_access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
        aws_secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)

        if aws_access_key and aws_secret_key:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                config=config,
            )
        else:
            # Use IAM role or environment credentials
            self.s3_client = boto3.client("s3", config=config)

        self.model_prefix = "ml_models/"
        self.dataset_prefix = "ml_datasets/"

    def upload_model(
        self,
        model_data: bytes,
        model_type: str,
        version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """
        Upload a trained model to S3.

        Args:
            model_data: Serialized model bytes
            model_type: Type of model (effort_prediction, etc.)
            version: Model version string
            metadata: Optional metadata to store with model

        Returns:
            Tuple of (s3_key, etag)

        Raises:
            RuntimeError: If upload fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            # Generate S3 key with timestamp for versioning
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = (
                f"{self.model_prefix}{model_type}/{version}/{timestamp}/model.joblib"
            )

            # Calculate MD5 checksum for data integrity
            md5_hash = hashlib.md5(model_data).hexdigest()

            # Prepare metadata
            upload_metadata = {
                "model_type": model_type,
                "version": version,
                "uploaded_at": timestamp,
                "md5_checksum": md5_hash,
            }

            if metadata:
                for key, value in metadata.items():
                    upload_metadata[f"custom_{key}"] = str(value)

            logger.info(
                f"Uploading model to S3: bucket={self.bucket_name}, "
                f"key={s3_key}, size={len(model_data)} bytes"
            )

            # Upload to S3 with metadata
            response = self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=model_data,
                Metadata=upload_metadata,
                ContentType="application/octet-stream",
            )

            etag = response.get("ETag", "").strip('"')

            logger.info(f"Model uploaded successfully: {s3_key} (ETag: {etag})")

            return s3_key, etag

        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to upload model to S3: {str(e)}")
            raise RuntimeError(f"S3 upload failed: {str(e)}") from e

    def download_model(self, s3_key: str) -> bytes:
        """
        Download a model from S3.

        Args:
            s3_key: S3 object key

        Returns:
            Model data as bytes

        Raises:
            RuntimeError: If download fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            logger.info(
                f"Downloading model from S3: bucket={self.bucket_name}, key={s3_key}"
            )

            # Download from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )

            model_data = response["Body"].read()

            logger.info(
                f"Model downloaded successfully: {s3_key}, "
                f"size={len(model_data)} bytes"
            )

            return model_data

        except self.s3_client.exceptions.NoSuchKey:
            logger.error(f"Model not found in S3: {s3_key}")
            raise RuntimeError(f"Model not found: {s3_key}")
        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to download model from S3: {str(e)}")
            raise RuntimeError(f"S3 download failed: {str(e)}") from e

    def download_model_to_file(self, s3_key: str, local_path: Path) -> None:
        """
        Download a model from S3 to a local file.

        Args:
            s3_key: S3 object key
            local_path: Local file path to save model

        Raises:
            RuntimeError: If download fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            logger.info(
                f"Downloading model to file: s3://{self.bucket_name}/{s3_key} "
                f"-> {local_path}"
            )

            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                str(local_path),
            )

            logger.info(f"Model saved to: {local_path}")

        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to download model to file: {str(e)}")
            raise RuntimeError(f"S3 download to file failed: {str(e)}") from e

    def upload_dataset(
        self,
        dataset_data: bytes,
        dataset_name: str,
        project_id: Optional[str] = None,
    ) -> str:
        """
        Upload a training dataset to S3.

        Args:
            dataset_data: Serialized dataset bytes
            dataset_name: Dataset identifier
            project_id: Optional project ID for organization

        Returns:
            S3 key of uploaded dataset

        Raises:
            RuntimeError: If upload fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            # Generate S3 key
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            if project_id:
                s3_key = (
                    f"{self.dataset_prefix}{project_id}/"
                    f"{dataset_name}_{timestamp}.pkl"
                )
            else:
                s3_key = f"{self.dataset_prefix}{dataset_name}_{timestamp}.pkl"

            logger.info(
                f"Uploading dataset to S3: bucket={self.bucket_name}, key={s3_key}"
            )

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=dataset_data,
                ContentType="application/octet-stream",
                Metadata={
                    "dataset_name": dataset_name,
                    "uploaded_at": timestamp,
                },
            )

            logger.info(f"Dataset uploaded successfully: {s3_key}")

            return s3_key

        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to upload dataset to S3: {str(e)}")
            raise RuntimeError(f"S3 dataset upload failed: {str(e)}") from e

    def download_dataset(self, s3_key: str) -> bytes:
        """
        Download a dataset from S3.

        Args:
            s3_key: S3 object key

        Returns:
            Dataset data as bytes

        Raises:
            RuntimeError: If download fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            logger.info(
                f"Downloading dataset from S3: bucket={self.bucket_name}, key={s3_key}"
            )

            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )

            dataset_data = response["Body"].read()

            logger.info(f"Dataset downloaded successfully: {s3_key}")

            return dataset_data

        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to download dataset from S3: {str(e)}")
            raise RuntimeError(f"S3 dataset download failed: {str(e)}") from e

    def list_models(
        self, model_type: Optional[str] = None, version: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List models in S3.

        Args:
            model_type: Filter by model type
            version: Filter by version

        Returns:
            List of model metadata dictionaries

        Raises:
            RuntimeError: If listing fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            # Build prefix
            prefix = self.model_prefix
            if model_type:
                prefix += f"{model_type}/"
                if version:
                    prefix += f"{version}/"

            logger.info(
                f"Listing models in S3: bucket={self.bucket_name}, prefix={prefix}"
            )

            models = []
            paginator = self.s3_client.get_paginator("list_objects_v2")

            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    models.append(
                        {
                            "key": obj["Key"],
                            "size": obj["Size"],
                            "last_modified": obj["LastModified"],
                            "etag": obj.get("ETag", "").strip('"'),
                        }
                    )

            logger.info(f"Found {len(models)} models in S3")

            return models

        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to list models in S3: {str(e)}")
            raise RuntimeError(f"S3 list failed: {str(e)}") from e

    def delete_model(self, s3_key: str) -> None:
        """
        Delete a model from S3.

        Args:
            s3_key: S3 object key

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            logger.info(
                f"Deleting model from S3: bucket={self.bucket_name}, key={s3_key}"
            )

            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )

            logger.info(f"Model deleted successfully: {s3_key}")

        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to delete model from S3: {str(e)}")
            raise RuntimeError(f"S3 delete failed: {str(e)}") from e

    def model_exists(self, s3_key: str) -> bool:
        """
        Check if a model exists in S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if model exists, False otherwise
        """
        try:
            if not self.bucket_name:
                return False

            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )

            return True

        except self.s3_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.exception(f"Error checking model existence: {str(e)}")
            return False

    def get_model_metadata(self, s3_key: str) -> Dict[str, Any]:
        """
        Get metadata for a model without downloading it.

        Args:
            s3_key: S3 object key

        Returns:
            Dictionary of model metadata

        Raises:
            RuntimeError: If metadata retrieval fails
        """
        try:
            if not self.bucket_name:
                raise RuntimeError("AWS_STORAGE_BUCKET_NAME not configured")

            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )

            return {
                "size": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "metadata": response.get("Metadata", {}),
            }

        except (BotoCoreError, ClientError) as e:
            logger.exception(f"Failed to get model metadata: {str(e)}")
            raise RuntimeError(f"S3 metadata retrieval failed: {str(e)}") from e
