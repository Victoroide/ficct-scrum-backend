"""
Prediction service for effort estimation, sprint duration, and story points.

Provides ML-powered predictions based on historical project data.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from django.db.models import Avg, Count, Q, Sum
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from apps.projects.models import Issue, Sprint

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for ML predictions (effort, duration, story points)."""

    def __init__(self):
        """Initialize prediction service."""
        self.effort_model = None
        self.story_points_model = None
        self.text_vectorizer = TfidfVectorizer(max_features=100, stop_words="english")

    def predict_issue_effort(
        self, title: str, description: str, issue_type: str, project_id: str
    ) -> Dict[str, Any]:
        """
        Predict effort (hours) required for an issue.

        Args:
            title: Issue title
            description: Issue description
            issue_type: Type of issue (bug, task, etc.)
            project_id: Project UUID

        Returns:
            Dictionary with predicted_hours, confidence, similar_issues
        """
        try:
            # Extract features from issue text
            features = self._extract_issue_features(title, description, issue_type, project_id)
            
            # Get similar completed issues for reference
            similar_issues = self._find_similar_completed_issues(title, description, project_id, limit=5)
            
            if not similar_issues:
                # No historical data - use heuristic
                avg_hours = self._get_average_effort_by_type(project_id, issue_type)
                return {
                    "predicted_hours": avg_hours,
                    "confidence": 0.3,
                    "similar_issues": [],
                    "method": "heuristic",
                    "reasoning": f"No similar issues found. Using average for {issue_type} in this project.",
                }
            
            # Calculate weighted prediction from similar issues
            similar_efforts = [issue["actual_hours"] for issue in similar_issues if issue["actual_hours"]]
            
            if similar_efforts:
                predicted_hours = float(np.mean(similar_efforts))
                confidence = min(0.7 + (len(similar_efforts) * 0.05), 0.95)
                
                return {
                    "predicted_hours": round(predicted_hours, 1),
                    "confidence": round(confidence, 2),
                    "prediction_range": {
                        "min": round(predicted_hours * 0.7, 1),
                        "max": round(predicted_hours * 1.3, 1),
                    },
                    "similar_issues": similar_issues,
                    "method": "similarity",
                    "reasoning": f"Based on {len(similar_efforts)} similar completed issues.",
                }
            
            # Fallback to type average
            avg_hours = self._get_average_effort_by_type(project_id, issue_type)
            return {
                "predicted_hours": avg_hours,
                "confidence": 0.4,
                "similar_issues": similar_issues,
                "method": "type_average",
                "reasoning": f"Similar issues found but no effort data. Using type average.",
            }
            
        except Exception as e:
            logger.exception(f"Error predicting effort: {str(e)}")
            raise

    def predict_sprint_duration(
        self, sprint_id: str, planned_issues: List[str], team_capacity_hours: float
    ) -> Dict[str, Any]:
        """
        Predict actual sprint completion time.

        Args:
            sprint_id: Sprint UUID
            planned_issues: List of issue IDs in sprint
            team_capacity_hours: Available team hours

        Returns:
            Dictionary with estimated_days, confidence, risk_factors
        """
        try:
            sprint = Sprint.objects.get(id=sprint_id)
            project = sprint.project
            
            # Get historical sprint data for velocity calculation
            past_sprints = Sprint.objects.filter(
                project=project, status="completed", completed_at__isnull=False
            ).order_by("-created_at")[:5]
            
            if not past_sprints:
                # No historical data
                planned_days = (sprint.end_date - sprint.start_date).days if sprint.end_date and sprint.start_date else 14
                return {
                    "estimated_days": planned_days,
                    "confidence": 0.2,
                    "risk_factors": ["No historical sprint data available"],
                    "method": "planned_duration",
                }
            
            # Calculate average velocity (story points per day)
            velocity_data = []
            for ps in past_sprints:
                duration = (ps.completed_at.date() - ps.start_date).days
                completed_points = ps.issues.filter(
                    status__is_final=True
                ).aggregate(total=Sum("story_points"))["total"] or 0
                
                if duration > 0:
                    velocity_data.append(completed_points / duration)
            
            if not velocity_data:
                avg_velocity = 0
            else:
                avg_velocity = float(np.mean(velocity_data))
            
            # Calculate total story points in planned issues
            total_points = Issue.objects.filter(
                id__in=planned_issues
            ).aggregate(total=Sum("story_points"))["total"] or 0
            
            # Estimate duration based on velocity
            if avg_velocity > 0:
                estimated_days = total_points / avg_velocity
                confidence = 0.7 if len(velocity_data) >= 3 else 0.5
            else:
                estimated_days = sprint.get_duration_days()
                confidence = 0.3
            
            # Identify risk factors
            risk_factors = []
            if total_points > avg_velocity * sprint.get_duration_days() * 1.2:
                risk_factors.append("Sprint may be overcommitted")
            if len(planned_issues) > 20:
                risk_factors.append("High number of issues may impact focus")
            
            return {
                "estimated_days": round(estimated_days, 1),
                "planned_days": sprint.get_duration_days(),
                "confidence": round(confidence, 2),
                "average_velocity": round(avg_velocity, 2),
                "total_story_points": total_points,
                "risk_factors": risk_factors,
                "method": "velocity_based",
            }
            
        except Exception as e:
            logger.exception(f"Error predicting sprint duration: {str(e)}")
            raise

    def recommend_story_points(
        self, title: str, description: str, issue_type: str, project_id: str
    ) -> Dict[str, Any]:
        """
        Recommend story points for an issue.

        Args:
            title: Issue title
            description: Issue description
            issue_type: Type of issue
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
                # Default recommendation based on type
                default_points = {"bug": 3, "task": 5, "story": 8, "epic": 13}
                points = default_points.get(issue_type, 5)
                
                return {
                    "recommended_points": points,
                    "confidence": 0.3,
                    "probability_distribution": {},
                    "reasoning": f"No similar issues found. Default for {issue_type}.",
                    "similar_issues": [],
                }
            
            # Calculate distribution of story points
            points_list = [issue["story_points"] for issue in similar_with_points]
            
            # Most common value
            from collections import Counter
            point_counts = Counter(points_list)
            most_common_points = point_counts.most_common(1)[0][0]
            
            # Calculate probability distribution
            total = len(points_list)
            distribution = {
                point: count / total for point, count in point_counts.items()
            }
            
            confidence = point_counts[most_common_points] / total
            
            return {
                "recommended_points": most_common_points,
                "confidence": round(confidence, 2),
                "probability_distribution": distribution,
                "reasoning": f"Based on {len(similar_with_points)} similar issues.",
                "similar_issues": similar_with_points[:5],
            }
            
        except Exception as e:
            logger.exception(f"Error recommending story points: {str(e)}")
            raise

    def _extract_issue_features(
        self, title: str, description: str, issue_type: str, project_id: str
    ) -> Dict[str, Any]:
        """Extract features from issue for ML models."""
        return {
            "title_length": len(title.split()),
            "description_length": len(description.split()) if description else 0,
            "has_description": bool(description),
            "issue_type": issue_type,
            "project_id": str(project_id),
        }

    def _find_similar_completed_issues(
        self, title: str, description: str, project_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find similar completed issues using text similarity."""
        try:
            # Get completed issues from project
            completed_issues = Issue.objects.filter(
                project_id=project_id,
                status__is_final=True,
                actual_hours__isnull=False,
            ).values(
                "id",
                "title",
                "description",
                "actual_hours",
                "story_points",
                "issue_type__name",
            )[:100]
            
            if not completed_issues:
                return []
            
            # Simple text similarity using keyword overlap
            query_text = f"{title} {description}".lower()
            query_words = set(query_text.split())
            
            scored_issues = []
            for issue in completed_issues:
                issue_text = f"{issue['title']} {issue['description'] or ''}".lower()
                issue_words = set(issue_text.split())
                
                # Jaccard similarity
                intersection = len(query_words & issue_words)
                union = len(query_words | issue_words)
                similarity = intersection / union if union > 0 else 0
                
                scored_issues.append({
                    "id": str(issue["id"]),
                    "title": issue["title"],
                    "issue_type": issue["issue_type__name"],
                    "actual_hours": issue["actual_hours"],
                    "story_points": issue["story_points"],
                    "similarity": similarity,
                })
            
            # Sort by similarity and return top matches
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
                issue_type__category=issue_type,
                actual_hours__isnull=False,
            ).aggregate(avg_hours=Avg("actual_hours"))["avg_hours"]
            
            return float(avg) if avg else 8.0  # Default 8 hours
        except Exception:
            return 8.0
