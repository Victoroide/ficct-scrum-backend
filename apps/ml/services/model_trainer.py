"""
Model training service with complete implementation.

Trains ML models using scikit-learn and stores them in S3.
"""

import io
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from apps.ml.models import MLModel, PredictionHistory
from apps.ml.services.s3_model_storage import S3ModelStorageService
from apps.projects.models import Issue

logger = logging.getLogger(__name__)


class ModelTrainer:
    """Service for training and managing ML models with S3 storage."""

    def __init__(self):
        """Initialize model trainer with S3 storage."""
        self.s3_storage = S3ModelStorageService()
        self.min_samples = 50  # Minimum training samples required

    def train_effort_prediction_model(
        self,
        project_id: Optional[str] = None,
        user=None,
    ) -> Optional[MLModel]:
        """
        Train effort prediction model using completed issues.

        Args:
            project_id: Optional project ID to train project-specific model
            user: User who initiated training

        Returns:
            Trained MLModel instance or None if insufficient data

        Raises:
            ValueError: If training data is invalid
            RuntimeError: If S3 upload fails
        """
        try:
            logger.info(
                f"Starting effort prediction model training "
                f"(project_id={project_id})"
            )

            # Fetch training data
            training_data = self._fetch_effort_training_data(project_id)

            if len(training_data) < self.min_samples:
                logger.warning(
                    f"Insufficient training data: {len(training_data)} samples "
                    f"(minimum: {self.min_samples})"
                )
                return None

            # Prepare features and labels
            X, y, feature_names = self._prepare_effort_features(training_data)

            if len(X) < self.min_samples:
                logger.warning(
                    f"Insufficient valid samples after preprocessing: {len(X)}"
                )
                return None

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Train model
            model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
            )

            logger.info(f"Training model on {len(X_train)} samples...")
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)

            logger.info(
                f"Model training complete: MAE={mae:.2f}, RMSE={rmse:.2f}, "
                f"R²={r2:.3f}"
            )

            # Serialize model and metadata
            model_bundle = {
                "model": model,
                "feature_names": feature_names,
                "scaler": None,  # Add scaler if needed
                "trained_at": datetime.utcnow().isoformat(),
            }

            model_bytes = self._serialize_model(model_bundle)

            # Upload to S3
            version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key, etag = self.s3_storage.upload_model(
                model_data=model_bytes,
                model_type="effort_prediction",
                version=version,
                metadata={
                    "project_id": project_id or "global",
                    "mae": mae,
                    "rmse": rmse,
                    "r2": r2,
                    "samples": len(training_data),
                },
            )

            # Create database record
            ml_model = MLModel.objects.create(
                name=f"Effort Prediction Model {version}",
                model_type="effort_prediction",
                version=version,
                status="active",
                is_active=True,
                s3_bucket=self.s3_storage.bucket_name,
                s3_key=s3_key,
                training_samples=len(training_data),
                trained_by=user,
                mae=mae,
                rmse=rmse,
                r2_score=r2,
                metadata={
                    "project_id": project_id,
                    "accuracy": r2,
                    "samples_count": len(training_data),
                    "feature_names": feature_names,
                },
                hyperparameters={
                    "n_estimators": 100,
                    "max_depth": 5,
                    "learning_rate": 0.1,
                },
                feature_importance=dict(
                    zip(feature_names, model.feature_importances_.tolist())
                ),
            )

            logger.info(
                f"Model saved to database and S3: {ml_model.id} "
                f"(s3://{self.s3_storage.bucket_name}/{s3_key})"
            )

            return ml_model

        except Exception as e:
            logger.exception(f"Error training effort prediction model: {str(e)}")
            raise

    def train_story_points_model(
        self,
        project_id: Optional[str] = None,
        user=None,
    ) -> Optional[MLModel]:
        """
        Train story points classification model.

        Args:
            project_id: Optional project ID
            user: User who initiated training

        Returns:
            Trained MLModel instance or None
        """
        try:
            logger.info(f"Training story points model (project_id={project_id})")

            # Fetch data
            training_data = self._fetch_story_points_training_data(project_id)

            if len(training_data) < self.min_samples:
                logger.warning(
                    f"Insufficient data for story points model: {len(training_data)}"
                )
                return None

            # For story points, we'll use a simpler similarity-based approach
            # Store the training data as the "model"
            model_bundle = {
                "training_data": training_data,
                "trained_at": datetime.utcnow().isoformat(),
            }

            model_bytes = self._serialize_model(model_bundle)

            # Upload to S3
            version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key, etag = self.s3_storage.upload_model(
                model_data=model_bytes,
                model_type="story_points",
                version=version,
                metadata={
                    "project_id": project_id or "global",
                    "samples": len(training_data),
                },
            )

            # Create database record
            ml_model = MLModel.objects.create(
                name=f"Story Points Model {version}",
                model_type="story_points",
                version=version,
                status="active",
                is_active=True,
                s3_bucket=self.s3_storage.bucket_name,
                s3_key=s3_key,
                training_samples=len(training_data),
                trained_by=user,
                metadata={
                    "project_id": project_id,
                    "samples_count": len(training_data),
                },
            )

            logger.info(f"Story points model saved: {ml_model.id}")

            return ml_model

        except Exception as e:
            logger.exception(f"Error training story points model: {str(e)}")
            raise

    def _fetch_effort_training_data(
        self, project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch completed issues with actual hours for training."""
        queryset = Issue.objects.filter(
            status__is_final=True,
            actual_hours__isnull=False,
            actual_hours__gt=0,
        ).select_related("issue_type", "project")

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        # Limit to recent data (last 2 years)
        two_years_ago = timezone.now() - timedelta(days=730)
        queryset = queryset.filter(created_at__gte=two_years_ago)

        training_data = []
        for issue in queryset[:10000]:  # Limit to prevent memory issues
            training_data.append(
                {
                    "id": str(issue.id),
                    "title": issue.title,
                    "description": issue.description or "",
                    "issue_type": issue.issue_type.name if issue.issue_type else "task",
                    "actual_hours": float(issue.actual_hours),
                    "story_points": issue.story_points or 0,
                    "priority": issue.priority or "P3",
                }
            )

        logger.info(f"Fetched {len(training_data)} training samples")
        return training_data

    def _fetch_story_points_training_data(
        self, project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch completed issues with story points."""
        queryset = Issue.objects.filter(
            status__is_final=True,
            story_points__isnull=False,
            story_points__gt=0,
        ).select_related("issue_type", "project")

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        training_data = []
        for issue in queryset[:10000]:
            training_data.append(
                {
                    "id": str(issue.id),
                    "title": issue.title,
                    "description": issue.description or "",
                    "issue_type": issue.issue_type.name if issue.issue_type else "task",
                    "story_points": issue.story_points,
                }
            )

        return training_data

    def _prepare_effort_features(
        self, training_data: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Extract features from training data.

        Returns:
            Tuple of (features, labels, feature_names)
        """
        features = []
        labels = []

        for item in training_data:
            # Text features
            title = item["title"]
            description = item["description"]
            combined_text = f"{title} {description}"

            # Numerical features
            title_length = len(title.split())
            desc_length = len(description.split()) if description else 0
            text_length = len(combined_text.split())

            # Issue type encoding
            issue_type = item["issue_type"].lower()
            is_bug = 1 if "bug" in issue_type else 0
            is_story = 1 if "story" in issue_type or "feature" in issue_type else 0
            is_task = 1 if "task" in issue_type else 0

            # Priority encoding
            priority = item.get("priority", "P3")
            priority_score = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}.get(priority, 1)

            # Story points if available
            story_points = item.get("story_points", 0)

            feature_vector = [
                title_length,
                desc_length,
                text_length,
                is_bug,
                is_story,
                is_task,
                priority_score,
                story_points,
            ]

            features.append(feature_vector)
            labels.append(item["actual_hours"])

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

        return np.array(features), np.array(labels), feature_names

    def _serialize_model(self, model_bundle: Dict[str, Any]) -> bytes:
        """Serialize model bundle to bytes using joblib."""
        buffer = io.BytesIO()
        joblib.dump(model_bundle, buffer)
        buffer.seek(0)
        return buffer.read()

    def should_retrain(self, ml_model: MLModel) -> bool:
        """
        Determine if a model should be retrained.

        Args:
            ml_model: Existing model to check

        Returns:
            True if retraining is recommended
        """
        try:
            # Check model age
            age_days = (timezone.now() - ml_model.training_date).days

            if age_days > 30:
                logger.info(
                    f"Model {ml_model.name} is {age_days} days old, "
                    "retraining recommended"
                )
                return True

            # Check if sufficient new data available
            project_id = ml_model.metadata.get("project_id")
            new_issues = Issue.objects.filter(
                status__is_final=True,
                actual_hours__isnull=False,
                updated_at__gte=ml_model.training_date,
            )

            if project_id:
                new_issues = new_issues.filter(project_id=project_id)

            new_count = new_issues.count()

            # Retrain if we have 20% more data
            threshold = ml_model.training_samples * 0.2

            if new_count >= threshold:
                logger.info(
                    f"Model {ml_model.name} has {new_count} new samples "
                    f"(threshold: {threshold}), retraining recommended"
                )
                return True

            # Check prediction accuracy degradation
            if self._check_accuracy_degradation(ml_model):
                logger.info(
                    f"Model {ml_model.name} accuracy has degraded, "
                    "retraining recommended"
                )
                return True

            return False

        except Exception as e:
            logger.exception(f"Error checking retrain status: {str(e)}")
            return False

    def _check_accuracy_degradation(self, ml_model: MLModel) -> bool:
        """Check if model accuracy has degraded based on recent predictions."""
        try:
            # Get recent predictions with actual values
            recent_predictions = PredictionHistory.objects.filter(
                model=ml_model,
                actual_value__isnull=False,
                created_at__gte=timezone.now() - timedelta(days=30),
            )[:100]

            if recent_predictions.count() < 20:
                return False  # Not enough data to evaluate

            # Calculate recent MAE
            errors = []
            for pred in recent_predictions:
                error = abs(pred.predicted_value - pred.actual_value)
                errors.append(error)

            recent_mae = np.mean(errors)
            original_mae = ml_model.mae or 0

            # If recent MAE is 50% worse, recommend retraining
            if original_mae > 0 and recent_mae > original_mae * 1.5:
                logger.warning(
                    f"Model accuracy degraded: recent MAE={recent_mae:.2f}, "
                    f"original MAE={original_mae:.2f}"
                )
                return True

            return False

        except Exception as e:
            logger.exception(f"Error checking accuracy degradation: {str(e)}")
            return False

    def evaluate_model(self, model_id: str) -> Dict[str, float]:
        """
        Evaluate a trained model on current data.

        Args:
            model_id: MLModel UUID

        Returns:
            Dictionary of evaluation metrics
        """
        try:
            ml_model = MLModel.objects.get(id=model_id)

            # Download model from S3
            model_bytes = self.s3_storage.download_model(ml_model.s3_key)
            model_bundle = joblib.load(io.BytesIO(model_bytes))

            # Fetch fresh test data
            project_id = ml_model.metadata.get("project_id")
            test_data = self._fetch_effort_training_data(project_id)

            if len(test_data) < 20:
                logger.warning("Insufficient test data for evaluation")
                return {"mae": 0.0, "rmse": 0.0, "r2": 0.0}

            # Prepare features
            X_test, y_test, _ = self._prepare_effort_features(test_data)

            # Make predictions
            model = model_bundle["model"]
            y_pred = model.predict(X_test)

            # Calculate metrics
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)

            metrics = {"mae": mae, "rmse": rmse, "r2": r2, "accuracy": r2}

            logger.info(
                f"Model evaluation complete: MAE={mae:.2f}, "
                f"RMSE={rmse:.2f}, R²={r2:.3f}"
            )

            return metrics

        except Exception as e:
            logger.exception(f"Error evaluating model: {str(e)}")
            return {"mae": 0.0, "rmse": 0.0, "r2": 0.0}
