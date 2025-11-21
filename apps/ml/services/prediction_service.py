"""
Enhanced prediction service with ML model integration and S3.

Provides ML-powered predictions with fallback to heuristics.
"""

import logging
from typing import Any, Dict, List, Optional

from django.db.models import Avg, Sum

import numpy as np

from apps.ml.models import MLModel, PredictionHistory
from apps.ml.services.model_loader import ModelLoader
from apps.projects.models import Issue, Sprint

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for ML predictions with model loading and fallback strategies."""

    def __init__(self):
        """Initialize prediction service."""
        self.model_loader = ModelLoader()

    def predict_issue_effort(
        self,
        title: str,
        description: str,
        issue_type: str,
        project_id: str,
        user=None,
    ) -> Dict[str, Any]:
        """
        Predict effort (hours) required for an issue.

        Uses trained ML model if available, falls back to similarity-based
        or heuristic methods.

        Args:
            title: Issue title
            description: Issue description
            issue_type: Type of issue (bug, task, etc.)
            project_id: Project UUID
            user: Optional user making the request

        Returns:
            Dictionary with predicted_hours, confidence, method, reasoning
        """
        try:
            # Try ML model first
            try:
                ml_prediction = self._predict_with_ml_model(
                    title, description, issue_type, project_id
                )
                if ml_prediction:
                    # Store prediction history
                    self._store_prediction_history(
                        model_id=ml_prediction["model_id"],
                        input_data={
                            "title": title,
                            "description": description,
                            "issue_type": issue_type,
                            "project_id": project_id,
                        },
                        predicted_value=ml_prediction["predicted_hours"],
                        confidence=ml_prediction["confidence"],
                        project_id=project_id,
                        user=user,
                    )
                    return ml_prediction
            except Exception as e:
                logger.warning(f"ML model prediction failed: {str(e)}, using fallback")

            # Fallback to similarity-based prediction
            similar_prediction = self._predict_with_similarity(
                title, description, issue_type, project_id
            )
            if similar_prediction["confidence"] > 0.5:
                return similar_prediction

            # Final fallback to heuristic
            return self._predict_with_heuristic(issue_type, project_id)

        except Exception as e:
            logger.exception(f"Error predicting effort: {str(e)}")
            # Return safe default
            return {
                "predicted_hours": 8.0,
                "confidence": 0.1,
                "method": "default",
                "reasoning": "Error occurred, using default estimate",
                "error": str(e),
            }

    def _predict_with_ml_model(
        self,
        title: str,
        description: str,
        issue_type: str,
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Make prediction using trained ML model.

        Args:
            title: Issue title
            description: Issue description
            issue_type: Issue type
            project_id: Project ID

        Returns:
            Prediction dict or None if model not available
        """
        try:
            # Load active model
            model_data = self.model_loader.load_active_model(
                model_type="effort_prediction",
                project_id=project_id,
            )

            if not model_data or not model_data.get("model"):
                logger.info("No ML model available for effort prediction")
                return None

            model = model_data["model"]
            scaler = model_data.get("scaler")
            feature_names = model_data.get("feature_names", [])

            # Prepare features
            features = self._extract_features_for_model(
                title, description, issue_type, feature_names
            )

            # Scale features if scaler is available
            if scaler is not None:
                features_scaled = scaler.transform([features])
                predicted_hours = float(model.predict(features_scaled)[0])
            else:
                predicted_hours = float(model.predict([features])[0])

            # Clamp to reasonable range
            predicted_hours = max(0.5, min(predicted_hours, 200.0))

            # Calculate confidence based on training metrics
            ml_model = model_data["ml_model"]
            base_confidence = ml_model.r2_score or 0.7

            # Adjust confidence based on uncertainty
            confidence = base_confidence * 0.9  # Slight reduction for production

            logger.info(
                f"ML model prediction: {predicted_hours:.1f} hours "
                f"(confidence: {confidence:.2f})"
            )

            return {
                "predicted_hours": round(predicted_hours, 1),
                "confidence": round(confidence, 2),
                "prediction_range": {
                    "min": round(predicted_hours * 0.7, 1),
                    "max": round(predicted_hours * 1.3, 1),
                },
                "method": "ml_model",
                "model_id": model_data["model_id"],
                "model_version": model_data["version"],
                "reasoning": f"Prediction from trained ML model (v{model_data['version']})",  # noqa: E501
                "similar_issues": [],
            }

        except Exception as e:
            logger.exception(f"Error in ML model prediction: {str(e)}")
            return None

    def _extract_features_for_model(
        self,
        title: str,
        description: str,
        issue_type: str,
        feature_names: List[str],
    ) -> List[float]:
        """
        Extract feature vector for ML model.

        Args:
            title: Issue title
            description: Issue description
            issue_type: Issue type
            feature_names: Expected feature names from model

        Returns:
            Feature vector matching model's expectations
        """
        # Calculate basic features
        title = title or ""
        description = description or ""
        combined_text = f"{title} {description}"

        title_length = len(title.split())
        desc_length = len(description.split())
        text_length = len(combined_text.split())

        # Issue type encoding with better granularity
        issue_type_lower = issue_type.lower()
        is_bug = 1 if "bug" in issue_type_lower else 0
        is_story = (
            1 if "story" in issue_type_lower or "feature" in issue_type_lower else 0
        )
        is_task = 1 if "task" in issue_type_lower else 0
        is_epic = 1 if "epic" in issue_type_lower else 0

        # Default priority
        priority_score = 2

        # Default story points (will be 0 for new issues)
        story_points = 0.0

        # Combined complexity score
        complexity_score = text_length * 0.1 + story_points * 2

        # Build feature vector matching expected order (10 features)
        features = [
            title_length,
            desc_length,
            text_length,
            is_bug,
            is_story,
            is_task,
            is_epic,
            priority_score,
            story_points,
            complexity_score,
        ]

        return features

    def _predict_with_similarity(
        self,
        title: str,
        description: str,
        issue_type: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Fallback: similarity-based prediction using completed issues."""
        similar_issues = self._find_similar_completed_issues(
            title, description, project_id, limit=5
        )

        if not similar_issues:
            return {
                "predicted_hours": 0.0,
                "confidence": 0.0,
                "method": "similarity",
                "similar_issues": [],
            }

        # Calculate weighted prediction
        similar_efforts = [
            issue["actual_hours"] for issue in similar_issues if issue["actual_hours"]
        ]

        if similar_efforts:
            predicted_hours = float(np.mean(similar_efforts))
            confidence = min(0.7 + (len(similar_efforts) * 0.05), 0.85)

            return {
                "predicted_hours": round(predicted_hours, 1),
                "confidence": round(confidence, 2),
                "prediction_range": {
                    "min": round(predicted_hours * 0.7, 1),
                    "max": round(predicted_hours * 1.3, 1),
                },
                "similar_issues": similar_issues,
                "method": "similarity",
                "reasoning": f"Based on {len(similar_efforts)} similar completed issues",  # noqa: E501
            }

        return {
            "predicted_hours": 0.0,
            "confidence": 0.0,
            "method": "similarity",
            "similar_issues": similar_issues,
        }

    def _predict_with_heuristic(
        self, issue_type: str, project_id: str
    ) -> Dict[str, Any]:
        """Final fallback: heuristic based on issue type."""
        avg_hours = self._get_average_effort_by_type(project_id, issue_type)

        return {
            "predicted_hours": avg_hours,
            "confidence": 0.3,
            "similar_issues": [],
            "method": "heuristic",
            "reasoning": f"No historical data. Using average for {issue_type}",
        }

    def predict_sprint_duration(
        self,
        sprint_id: str,
        planned_issues: List[str],
        team_capacity_hours: float,
    ) -> Dict[str, Any]:
        """
        Predict actual sprint completion time.

        Uses Sprint model fields: start_date, end_date, committed_points, completed_points.  # noqa: E501

        Args:
            sprint_id: Sprint UUID
            planned_issues: List of issue IDs (optional)
            team_capacity_hours: Available hours (optional)

        Returns:
            Dictionary with estimated_days, confidence, risk_factors
        """
        try:
            sprint = Sprint.objects.select_related("project").get(id=sprint_id)

            logger.info(f"[ML] Predicting duration for sprint {sprint.name}")

            # Method 1: Use sprint dates if available
            if sprint.start_date and sprint.end_date:
                duration_days = (sprint.end_date - sprint.start_date).days
                logger.info(f"[ML] Using sprint dates: {duration_days} days")
                return {
                    "estimated_days": duration_days,
                    "planned_days": duration_days,
                    "confidence": 0.95,
                    "risk_factors": [],
                    "method": "from_sprint_dates",
                }

            # Method 2: Calculate from estimated hours
            total_estimated_hours = sprint.issues.filter(
                is_active=True, estimated_hours__isnull=False
            ).aggregate(total=Sum("estimated_hours"))["total"]

            if total_estimated_hours and total_estimated_hours > 0:
                hours_per_day = 8
                estimated_days = float(total_estimated_hours) / hours_per_day
                logger.info(f"[ML] Using estimated hours: {estimated_days} days")
                return {
                    "estimated_days": int(round(estimated_days)),
                    "planned_days": int(round(estimated_days)),
                    "confidence": 0.7,
                    "total_estimated_hours": float(total_estimated_hours),
                    "hours_per_day": hours_per_day,
                    "risk_factors": [],
                    "method": "from_estimated_hours",
                }

            # Method 3: Velocity-based calculation
            total_points = sprint.issues.filter(
                is_active=True, story_points__isnull=False
            ).aggregate(total=Sum("story_points"))["total"]

            if total_points and total_points > 0:
                pass

                past_sprints = Sprint.objects.filter(
                    project=sprint.project,
                    status="completed",
                    completed_at__isnull=False,
                    start_date__isnull=False,
                ).order_by("-completed_at")[:5]

                velocity_data = []
                for ps in past_sprints:
                    duration = (ps.completed_at.date() - ps.start_date).days
                    if duration > 0 and ps.completed_points > 0:
                        velocity_data.append(float(ps.completed_points) / duration)

                if velocity_data:
                    avg_velocity = float(np.mean(velocity_data))
                    estimated_days = (
                        total_points / avg_velocity if avg_velocity > 0 else 14
                    )
                    logger.info(f"[ML] Using velocity: {estimated_days} days")
                    return {
                        "estimated_days": int(round(estimated_days)),
                        "planned_days": int(round(estimated_days)),
                        "confidence": 0.7 if len(velocity_data) >= 3 else 0.5,
                        "average_velocity": round(avg_velocity, 2),
                        "total_story_points": total_points,
                        "risk_factors": [],
                        "method": "velocity_based",
                    }

            # Method 4: Default fallback
            logger.info("[ML] Using default duration: 14 days")
            return {
                "estimated_days": 14,
                "planned_days": 14,
                "confidence": 0.0,
                "risk_factors": ["No historical data or estimates available"],
                "method": "default",
            }

        except Sprint.DoesNotExist:
            logger.error(f"[ML] Sprint {sprint_id} not found")
            return {
                "estimated_days": 14,
                "planned_days": 14,
                "confidence": 0.0,
                "risk_factors": ["Sprint not found"],
                "method": "default",
                "error": "Sprint does not exist",
            }
        except Exception as e:
            logger.exception(f"[ML] Error predicting sprint duration: {str(e)}")
            return {
                "estimated_days": 14,
                "planned_days": 14,
                "confidence": 0.0,
                "risk_factors": ["Error in prediction"],
                "method": "default",
                "error": str(e),
            }

    def recommend_story_points(
        self,
        title: str,
        description: str,
        issue_type: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """
        Recommend story points for an issue.

        Args:
            title: Issue title
            description: Issue description
            issue_type: Issue type
            project_id: Project UUID

        Returns:
            Dictionary with recommended_points, confidence, reasoning
        """
        try:
            # Find similar issues with story points
            similar_issues = self._find_similar_completed_issues(
                title, description, project_id, limit=10
            )

            similar_with_points = [
                issue for issue in similar_issues if issue.get("story_points")
            ]

            if not similar_with_points:
                # Default based on type
                default_points = {"bug": 3, "task": 5, "story": 8, "epic": 13}
                points = default_points.get(issue_type.lower(), 5)

                return {
                    "recommended_points": points,
                    "confidence": 0.3,
                    "probability_distribution": {},
                    "reasoning": f"No similar issues found. Default for {issue_type}",
                    "similar_issues": [],
                    "method": "heuristic",
                }

            # Calculate distribution
            points_list = [issue["story_points"] for issue in similar_with_points]

            from collections import Counter

            point_counts = Counter(points_list)
            most_common_points = point_counts.most_common(1)[0][0]

            # Probability distribution
            total = len(points_list)
            distribution = {
                point: count / total for point, count in point_counts.items()
            }

            confidence = point_counts[most_common_points] / total

            return {
                "recommended_points": most_common_points,
                "confidence": round(confidence, 2),
                "probability_distribution": distribution,
                "reasoning": f"Based on {len(similar_with_points)} similar issues",
                "similar_issues": similar_with_points[:5],
                "method": "similarity",
            }

        except Exception as e:
            logger.exception(f"Error recommending story points: {str(e)}")
            return {
                "recommended_points": 5,
                "confidence": 0.2,
                "method": "default",
                "error": str(e),
            }

    def _find_similar_completed_issues(
        self, title: str, description: str, project_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find similar completed issues using text similarity."""
        try:
            completed_issues = Issue.objects.filter(
                project_id=project_id,
                status__is_final=True,
                actual_hours__isnull=False,
            ).select_related("issue_type")[:100]

            if not completed_issues:
                return []

            # Simple text similarity
            query_text = f"{title} {description}".lower()
            query_words = set(query_text.split())

            scored_issues = []
            for issue in completed_issues:
                issue_text = f"{issue.title} {issue.description or ''}".lower()
                issue_words = set(issue_text.split())

                # Jaccard similarity
                intersection = len(query_words & issue_words)
                union = len(query_words | issue_words)
                similarity = intersection / union if union > 0 else 0

                scored_issues.append(
                    {
                        "id": str(issue.id),
                        "title": issue.title,
                        "issue_type": (
                            issue.issue_type.name if issue.issue_type else "task"
                        ),
                        "actual_hours": issue.actual_hours,
                        "story_points": issue.story_points,
                        "similarity": similarity,
                    }
                )

            scored_issues.sort(key=lambda x: x["similarity"], reverse=True)
            return scored_issues[:limit]

        except Exception as e:
            logger.exception(f"Error finding similar issues: {str(e)}")
            return []

    def _get_average_effort_by_type(self, project_id: str, issue_type: str) -> float:
        """Get average effort for issue type in project."""
        try:
            avg = Issue.objects.filter(
                project_id=project_id,
                issue_type__name__icontains=issue_type,
                actual_hours__isnull=False,
            ).aggregate(avg_hours=Avg("actual_hours"))["avg_hours"]

            return float(avg) if avg else 8.0
        except Exception:
            return 8.0

    def _store_prediction_history(
        self,
        model_id: str,
        input_data: Dict[str, Any],
        predicted_value: float,
        confidence: float,
        project_id: str,
        user=None,
    ) -> None:
        """Store prediction in history for tracking and model improvement."""
        try:
            ml_model = MLModel.objects.get(id=model_id)

            PredictionHistory.objects.create(
                model=ml_model,
                input_data=input_data,
                predicted_value=predicted_value,
                confidence_score=confidence,
                project_id=project_id,
                requested_by=user,
            )

            logger.debug(f"Stored prediction history for model {model_id}")

        except Exception as e:
            logger.warning(f"Failed to store prediction history: {str(e)}")
