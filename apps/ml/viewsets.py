"""
Machine Learning ViewSets for predictions and recommendations.

Provides REST API endpoints for ML-powered features.
"""

import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ml.services import (
    AnomalyDetectionService,
    PredictionService,
    RecommendationService,
)
from apps.projects.permissions import CanAccessProject
from apps.reporting.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class MLViewSet(viewsets.ViewSet):
    """Machine Learning predictions and recommendations."""

    permission_classes = [IsAuthenticated, CanAccessProject]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prediction_service = PredictionService()
        self.recommendation_service = RecommendationService()
        self.anomaly_service = AnomalyDetectionService()

    @extend_schema(
        tags=["Machine Learning"],
        summary="Predict issue effort",
        description="Predict story points or hours required for an issue based on historical data",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "issue_type": {"type": "string"},
                    "project_id": {"type": "string", "format": "uuid"},
                },
                "required": ["title", "issue_type", "project_id"],
            }
        },
        responses={
            200: {
                "description": "Prediction successful",
                "content": {
                    "application/json": {
                        "example": {
                            "predicted_hours": 8.5,
                            "confidence": 0.75,
                            "prediction_range": {"min": 6.0, "max": 11.0},
                            "similar_issues": [],
                            "method": "similarity",
                            "reasoning": "Based on 5 similar completed issues.",
                        }
                    }
                },
            }
        },
    )
    @action(detail=False, methods=["post"], url_path="predict-effort")
    def predict_effort(self, request):
        """Predict effort required for an issue."""
        from rest_framework.exceptions import PermissionDenied
        
        try:
            title = request.data.get("title")
            description = request.data.get("description", "")
            issue_type = request.data.get("issue_type")
            project_id = request.data.get("project_id")

            if not all([title, issue_type, project_id]):
                return Response(
                    {"error": "title, issue_type, and project_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check user has access to project
            from apps.projects.models import Project
            try:
                project = Project.objects.get(id=project_id)
                self.check_object_permissions(request, project)
            except Project.DoesNotExist:
                return Response(
                    {"error": "Project not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            prediction = self.prediction_service.predict_issue_effort(
                title=title,
                description=description,
                issue_type=issue_type,
                project_id=project_id,
            )

            return Response(prediction, status=status.HTTP_200_OK)

        except PermissionDenied:
            raise
        except Exception as e:
            logger.exception(f"Error predicting effort: {str(e)}")
            return Response(
                {"error": "Failed to predict effort. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Machine Learning"],
        summary="Estimate sprint duration",
        description="Predict actual sprint completion time based on planned scope and team velocity",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "sprint_id": {"type": "string", "format": "uuid"},
                    "planned_issues": {"type": "array", "items": {"type": "string"}},
                    "team_capacity_hours": {"type": "number"},
                },
                "required": ["sprint_id"],
            }
        },
    )
    @action(detail=False, methods=["post"], url_path="estimate-sprint-duration")
    def estimate_sprint_duration(self, request):
        """Estimate sprint duration based on velocity."""
        sprint_id = None
        try:
            sprint_id = request.data.get("sprint_id")
            planned_issues = request.data.get("planned_issues", [])
            team_capacity_hours = request.data.get("team_capacity_hours", 0)

            if not sprint_id:
                logger.warning("[ML] Missing sprint_id in estimate_sprint_duration request")
                return Response(
                    {"error": "sprint_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            logger.info(f"[ML] Estimating duration for sprint {sprint_id}")

            estimation = self.prediction_service.predict_sprint_duration(
                sprint_id=sprint_id,
                planned_issues=planned_issues,
                team_capacity_hours=team_capacity_hours,
            )

            logger.info(
                f"[ML] Sprint duration estimated: {estimation.get('estimated_days')} days "
                f"(confidence: {estimation.get('confidence')})"
            )

            return Response(estimation, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"[ML] Error estimating sprint duration for {sprint_id}: {str(e)}")
            return Response(
                {"error": "Failed to estimate sprint duration.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Machine Learning"],
        summary="Recommend story points",
        description="Suggest story point estimation for an issue based on historical data",
    )
    @action(detail=False, methods=["post"], url_path="recommend-story-points")
    def recommend_story_points(self, request):
        """Recommend story points for an issue."""
        try:
            title = request.data.get("title")
            description = request.data.get("description", "")
            issue_type = request.data.get("issue_type")
            project_id = request.data.get("project_id")

            if not all([title, issue_type, project_id]):
                return Response(
                    {"error": "title, issue_type, and project_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            recommendation = self.prediction_service.recommend_story_points(
                title=title,
                description=description,
                issue_type=issue_type,
                project_id=project_id,
            )

            return Response(recommendation, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error recommending story points: {str(e)}")
            return Response(
                {"error": "Failed to recommend story points."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Machine Learning"],
        summary="Suggest task assignment",
        description="Recommend best team members for an issue based on skills, workload, and performance",
    )
    @action(detail=False, methods=["post"], url_path="suggest-assignment")
    def suggest_assignment(self, request):
        """Suggest team member for issue assignment."""
        try:
            issue_id = request.data.get("issue_id")
            project_id = request.data.get("project_id")
            top_n = request.data.get("top_n", 3)

            if not all([issue_id, project_id]):
                return Response(
                    {"error": "issue_id and project_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            suggestions = self.recommendation_service.suggest_task_assignment(
                issue_id=issue_id, project_id=project_id, top_n=top_n
            )

            return Response({"suggestions": suggestions}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error suggesting assignment: {str(e)}")
            return Response(
                {"error": "Failed to suggest assignment."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Machine Learning"],
        summary="Identify sprint risks",
        description="Detect if a sprint is at risk of missing deadlines with mitigation suggestions",
        parameters=[
            OpenApiParameter(
                name="sprint_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="Sprint UUID",
            )
        ],
    )
    @action(detail=True, methods=["get"], url_path="sprint-risk")
    def sprint_risk(self, request, pk=None):
        """Detect sprint risks."""
        try:
            logger.info(f"[ML] Detecting risks for sprint {pk}")
            
            risks = self.anomaly_service.detect_sprint_risks(sprint_id=pk)
            
            logger.info(f"[ML] Sprint risk detection complete: {len(risks)} risk(s) found")
            
            return Response({"risks": risks}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"[ML] Error detecting sprint risks for {pk}: {str(e)}")
            return Response(
                {"error": "Failed to detect sprint risks.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Machine Learning"],
        summary="Generate AI Project Summary Report",
        description="Generate comprehensive AI-powered project report with completion %, velocity, and risk score",
        parameters=[
            OpenApiParameter(
                name="project_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="Project UUID",
            )
        ],
        responses={
            200: {
                "description": "Project summary generated successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "completion": 37.5,
                            "velocity": 15.3,
                            "risk_score": 23.5,
                            "project_id": "77cc72d2-1911-4d6c-a6cc-bfb899ba96cd",
                            "generated_at": "2025-11-16T01:00:00Z"
                        }
                    }
                },
            },
            404: OpenApiResponse(description="Project not found"),
        },
    )
    @action(
        detail=True,
        methods=["post", "get"],
        url_path="project-summary",
        url_name="project-summary"
    )
    def project_summary(self, request, pk=None):
        """
        Generate AI Project Summary Report with key metrics.
        
        Consolidates:
        - Completion % (from issues)
        - Velocity (from sprints)
        - Risk Score (from ML anomalies + project health)
        """
        try:
            from apps.projects.models import Project, Issue, Sprint
            from django.db.models import Sum, Count, Q
            from django.db.models.functions import Coalesce
            from django.utils import timezone
            
            logger.info(f"[ML] Generating project summary for {pk}")
            
            # Verify project exists
            try:
                project = Project.objects.get(id=pk)
                self.check_object_permissions(request, project)
            except Project.DoesNotExist:
                return Response(
                    {"error": "Project not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Calculate Completion %
            total_issues = Issue.objects.filter(project=project, is_active=True).count()
            completed_issues = Issue.objects.filter(
                project=project, is_active=True, status__category="done"
            ).count()
            
            completion = round((completed_issues / total_issues) * 100, 2) if total_issues > 0 else 0.0
            
            # Calculate Velocity (average from active + completed sprints)
            sprints = Sprint.objects.filter(
                project=project, status__in=["active", "completed"]
            ).order_by("-end_date")[:5]
            
            velocities = []
            for sprint in sprints:
                completed_points = sprint.issues.filter(
                    status__category="done", is_active=True
                ).aggregate(total=Coalesce(Sum("story_points"), 0))["total"]
                
                if completed_points > 0:
                    velocities.append(completed_points)
            
            velocity = round(sum(velocities) / len(velocities), 2) if velocities else 0.0
            
            # Calculate Risk Score
            risk_score = 0.0
            
            # Factor 1: Unassigned issues (max 30 points)
            unassigned_count = Issue.objects.filter(
                project=project, is_active=True, assignee__isnull=True
            ).count()
            if total_issues > 0:
                risk_score += min((unassigned_count / total_issues) * 100, 30)
            
            # Factor 2: Overdue issues (max 40 points)
            overdue_issues = Issue.objects.filter(
                project=project,
                is_active=True,
                sprint__end_date__lt=timezone.now().date(),
                status__category__in=["to_do", "in_progress"]  # Fixed: to_do not todo
            ).count()
            if total_issues > 0:
                risk_score += min((overdue_issues / total_issues) * 100, 40)
            
            # Factor 3: Velocity decline (max 30 points)
            if len(velocities) >= 2:
                recent_velocity = sum(velocities[:2]) / 2
                older_velocity = sum(velocities[2:]) / len(velocities[2:]) if len(velocities) > 2 else recent_velocity
                
                if older_velocity > 0:
                    velocity_change = ((recent_velocity - older_velocity) / older_velocity) * 100
                    if velocity_change < -20:  # Velocity dropped > 20%
                        risk_score += min(abs(velocity_change), 30)
            
            risk_score = min(round(risk_score, 2), 100.0)
            
            logger.info(
                f"[ML] Project summary generated: completion={completion}%, "
                f"velocity={velocity}, risk_score={risk_score}, "
                f"total_issues={total_issues}, completed={completed_issues}, "
                f"sprints_analyzed={len(velocities)}, velocities={velocities}"
            )
            
            return Response(
                {
                    "completion": completion,
                    "velocity": velocity,
                    "risk_score": risk_score,
                    "project_id": str(pk),
                    "generated_at": timezone.now().isoformat(),
                    "metrics_breakdown": {
                        "total_issues": total_issues,
                        "completed_issues": completed_issues,
                        "sprints_analyzed": len(velocities),
                        "unassigned_issues": unassigned_count,
                        "overdue_issues": overdue_issues,
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.exception(f"[ML] Error generating project summary for {pk}: {str(e)}")
            return Response(
                {"error": "Failed to generate project summary.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Machine Learning"],
        summary="Detect project anomalies",
        description="Identify unusual patterns in project (velocity drops, bottlenecks, etc.)",
        parameters=[
            OpenApiParameter(
                name="project_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="Project UUID",
            )
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="project-anomalies/(?P<pk>[^/.]+)",
        url_name="project-anomalies"
    )
    def detect_anomalies(self, request, pk=None):
        """Detect project anomalies."""
        try:
            from apps.ml.models import AnomalyDetection
            anomalies = list(AnomalyDetection.objects.filter(project_id=pk).values(
                'id', 'anomaly_type', 'severity', 'description', 'created_at'
            ))
            return Response(anomalies, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error detecting anomalies: {str(e)}")
            return Response(
                {"error": "Failed to detect anomalies."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
