"""
Model loader service with S3 integration and caching.

Loads trained models from S3 with in-memory caching for performance.
"""

import io
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from django.core.cache import cache
from django.utils import timezone

import joblib

from apps.ml.models import MLModel
from apps.ml.services.s3_model_storage import S3ModelStorageService

logger = logging.getLogger(__name__)


class ModelLoader:
    """Service for loading and caching ML models from S3."""

    # Class-level cache with thread safety
    _model_cache: Dict[str, Dict[str, Any]] = {}
    _cache_lock = threading.Lock()

    # Cache TTL in seconds
    CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        """Initialize model loader."""
        self.s3_storage = S3ModelStorageService()

    def load_active_model(
        self,
        model_type: str,
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Load the active model for a given type.

        Args:
            model_type: Type of model to load
            project_id: Optional project ID for project-specific models

        Returns:
            Dictionary containing model and metadata, or None

        Raises:
            RuntimeError: If model loading fails
        """
        try:
            # Build cache key
            cache_key = self._build_cache_key(model_type, project_id)

            # Check memory cache first
            cached_model = self._get_from_cache(cache_key)
            if cached_model:
                logger.debug(f"Model loaded from cache: {cache_key}")
                return cached_model

            # Query database for active model
            queryset = MLModel.objects.filter(
                model_type=model_type,
                status="active",
                is_active=True,
            )

            if project_id:
                # Try project-specific model first
                ml_model = (
                    queryset.filter(metadata__project_id=project_id)
                    .order_by("-training_date")
                    .first()
                )

                if not ml_model:
                    # Fallback to global model
                    ml_model = (
                        queryset.filter(metadata__project_id__isnull=True)
                        .order_by("-training_date")
                        .first()
                    )
            else:
                ml_model = queryset.order_by("-training_date").first()

            if not ml_model:
                logger.warning(
                    f"No active model found: type={model_type}, "
                    f"project_id={project_id}"
                )
                return None

            # Load model from S3
            model_bundle = self._load_model_from_s3(ml_model)

            # Add metadata
            model_data = {
                "model": model_bundle.get("model"),
                "model_bundle": model_bundle,
                "ml_model": ml_model,
                "model_id": str(ml_model.id),
                "version": ml_model.version,
                "trained_at": ml_model.training_date,
                "feature_names": model_bundle.get("feature_names", []),
                "metadata": ml_model.metadata,
            }

            # Cache the loaded model
            self._put_in_cache(cache_key, model_data)

            logger.info(
                f"Model loaded successfully: {ml_model.name} " f"(v{ml_model.version})"
            )

            return model_data

        except Exception as e:
            logger.exception(f"Error loading model: {str(e)}")
            raise RuntimeError(f"Failed to load model: {str(e)}") from e

    def load_model_by_id(self, model_id: str) -> Dict[str, Any]:
        """
        Load a specific model by ID.

        Args:
            model_id: MLModel UUID

        Returns:
            Dictionary containing model and metadata

        Raises:
            RuntimeError: If model loading fails
        """
        try:
            # Check cache
            cache_key = f"model_id_{model_id}"
            cached_model = self._get_from_cache(cache_key)
            if cached_model:
                return cached_model

            # Load from database
            ml_model = MLModel.objects.get(id=model_id)

            # Load from S3
            model_bundle = self._load_model_from_s3(ml_model)

            model_data = {
                "model": model_bundle.get("model"),
                "model_bundle": model_bundle,
                "ml_model": ml_model,
                "model_id": str(ml_model.id),
                "version": ml_model.version,
                "trained_at": ml_model.training_date,
                "feature_names": model_bundle.get("feature_names", []),
                "metadata": ml_model.metadata,
            }

            # Cache
            self._put_in_cache(cache_key, model_data)

            return model_data

        except MLModel.DoesNotExist:
            raise RuntimeError(f"Model not found: {model_id}")
        except Exception as e:
            logger.exception(f"Error loading model by ID: {str(e)}")
            raise RuntimeError(f"Failed to load model: {str(e)}") from e

    def _load_model_from_s3(self, ml_model: MLModel) -> Dict[str, Any]:
        """
        Load model bundle from S3.

        Args:
            ml_model: MLModel database instance

        Returns:
            Deserialized model bundle

        Raises:
            RuntimeError: If S3 download or deserialization fails
        """
        try:
            if not ml_model.s3_key:
                raise RuntimeError(f"Model {ml_model.id} has no S3 key")

            # Download from S3
            model_bytes = self.s3_storage.download_model(ml_model.s3_key)

            # Deserialize
            model_bundle = joblib.load(io.BytesIO(model_bytes))

            return model_bundle

        except Exception as e:
            logger.exception(
                f"Error loading model from S3: {ml_model.s3_key}, {str(e)}"
            )
            raise RuntimeError(f"S3 model load failed: {str(e)}") from e

    def clear_cache(self, model_type: Optional[str] = None) -> None:
        """
        Clear model cache.

        Args:
            model_type: If specified, only clear this model type
        """
        with self._cache_lock:
            if model_type:
                # Clear specific model type
                keys_to_remove = [
                    key
                    for key in self._model_cache.keys()
                    if key.startswith(f"{model_type}_")
                ]
                for key in keys_to_remove:
                    del self._model_cache[key]
                logger.info(f"Cleared cache for model type: {model_type}")
            else:
                # Clear all
                self._model_cache.clear()
                logger.info("Cleared all model cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._cache_lock:
            total_cached = len(self._model_cache)
            cached_models = list(self._model_cache.keys())

            return {
                "total_cached": total_cached,
                "cached_keys": cached_models,
                "cache_ttl_seconds": self.CACHE_TTL,
            }

    def _build_cache_key(
        self, model_type: str, project_id: Optional[str] = None
    ) -> str:
        """Build cache key for model."""
        if project_id:
            return f"{model_type}_project_{project_id}"
        return f"{model_type}_global"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get model from cache if not expired.

        Args:
            cache_key: Cache key

        Returns:
            Cached model data or None
        """
        with self._cache_lock:
            if cache_key not in self._model_cache:
                return None

            cached_data = self._model_cache[cache_key]
            cached_at = cached_data.get("cached_at")

            # Check if expired
            if cached_at:
                age_seconds = (datetime.utcnow() - cached_at).total_seconds()
                if age_seconds > self.CACHE_TTL:
                    # Expired, remove from cache
                    del self._model_cache[cache_key]
                    logger.debug(f"Cache expired: {cache_key}")
                    return None

            return cached_data.get("data")

    def _put_in_cache(self, cache_key: str, model_data: Dict[str, Any]) -> None:
        """
        Store model in cache.

        Args:
            cache_key: Cache key
            model_data: Model data to cache
        """
        with self._cache_lock:
            self._model_cache[cache_key] = {
                "data": model_data,
                "cached_at": datetime.utcnow(),
            }
            logger.debug(f"Model cached: {cache_key}")

    def preload_models(self, model_types: Optional[list] = None) -> Dict[str, bool]:
        """
        Preload models into cache for faster first predictions.

        Args:
            model_types: List of model types to preload, or None for all

        Returns:
            Dictionary of model_type -> success status
        """
        if model_types is None:
            model_types = [
                "effort_prediction",
                "sprint_duration",
                "story_points",
                "task_assignment",
                "risk_detection",
                "anomaly_detection",
            ]

        results = {}

        for model_type in model_types:
            try:
                model_data = self.load_active_model(model_type)
                results[model_type] = model_data is not None
                if model_data:
                    logger.info(f"Preloaded model: {model_type}")
            except Exception as e:
                logger.warning(f"Failed to preload {model_type}: {str(e)}")
                results[model_type] = False

        return results
