from datetime import datetime

from django.db import models, transaction

from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Sprint
from apps.projects.permissions import CanAccessProject, CanManageSprint
from apps.projects.serializers import (
    SprintCreateSerializer,
    SprintDetailSerializer,
    SprintListSerializer,
    SprintUpdateSerializer,
)


class SprintFilter(filters.FilterSet):
    project = filters.UUIDFilter(field_name="project__id")
    status = filters.ChoiceFilter(choices=Sprint.STATUS_CHOICES)

    class Meta:
        model = Sprint
        fields = ["project", "status"]


@extend_schema_view(
    list=extend_schema(
        tags=["Sprints"],
        operation_id="sprints_list",
        summary="List Sprints",
    ),
    retrieve=extend_schema(
        tags=["Sprints"],
        operation_id="sprints_retrieve",
        summary="Get Sprint Details",
    ),
    create=extend_schema(
        tags=["Sprints"],
        operation_id="sprints_create",
        summary="Create Sprint ",
    ),
    update=extend_schema(
        tags=["Sprints"],
        operation_id="sprints_update",
        summary="Update Sprint ",
    ),
    partial_update=extend_schema(
        tags=["Sprints"],
        operation_id="sprints_partial_update",
        summary="Partial Update Sprint",
    ),
    destroy=extend_schema(
        tags=["Sprints"],
        operation_id="sprints_destroy",
        summary="Delete Sprint",
    ),
)
class SprintViewSet(viewsets.ModelViewSet):
    queryset = Sprint.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_class = SprintFilter
    ordering_fields = ["start_date", "end_date", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        from django.db.models import Count, Q

        return (
            Sprint.objects.filter(
                Q(
                    project__workspace__members__user=self.request.user,
                    project__workspace__members__is_active=True,
                )
                | Q(
                    project__team_members__user=self.request.user,
                    project__team_members__is_active=True,
                )
            )
            .select_related("project", "project__workspace", "created_by")
            .annotate(
                # Pre-calculate counts to avoid N queries
                _issue_count=Count(
                    "issues", filter=Q(issues__is_active=True), distinct=True
                ),
                _completed_issue_count=Count(
                    "issues",
                    filter=Q(issues__is_active=True, issues__status__is_final=True),
                    distinct=True,
                ),
            )
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return SprintCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return SprintUpdateSerializer
        elif self.action == "retrieve":
            return SprintDetailSerializer
        return SprintListSerializer

    def get_permissions(self):
        """
        Define granular permissions for sprint operations.

        PERMISSION LOGIC:
        - Structural Management (create, update, delete): Requires CanManageSprint
          → Only project lead/admin can create/edit/delete sprint structure

        - Sprint Operations (start, complete, add_issue, remove_issue): Requires CanAccessProject  # noqa: E501
          → Any project or workspace member can operate sprints

        - Read Operations (list, retrieve, progress, burndown): Requires CanAccessProject  # noqa: E501
          → Any project or workspace member can view sprints
        """
        # Structural management requires admin/lead role
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), CanManageSprint()]

        # All other operations (including custom actions) require project access only
        # Custom actions: start_sprint, complete_sprint, add_issue, remove_issue,
        # progress, burndown
        return [IsAuthenticated(), CanAccessProject()]

    @transaction.atomic
    def perform_create(self, serializer):
        sprint = serializer.save()

        LoggerService.log_info(
            action="sprint_created",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "sprint_id": str(sprint.id),
                "sprint_name": sprint.name,
                "project_id": str(sprint.project.id),
            },
        )

    @extend_schema(
        tags=["Sprints"],
        operation_id="sprints_start",
        summary="Start Sprint ",
        description="Start a sprint. Only one active sprint allowed per project. Sprint must have issues.",  # noqa: E501
    )
    @action(detail=True, methods=["post"], url_path="start")
    def start_sprint(self, request, pk=None):
        sprint = self.get_object()

        if sprint.status == "active":
            return Response(
                {"error": "Sprint is already active"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if sprint.status == "completed":
            return Response(
                {"error": "Cannot start a completed sprint"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Sprint.objects.filter(project=sprint.project, status="active").exists():
            return Response(
                {"error": "Another sprint is already active in this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not sprint.issues.filter(is_active=True).exists():
            return Response(
                {"error": "Sprint must have at least one issue before starting"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sprint.status = "active"
        if not sprint.start_date:
            sprint.start_date = datetime.now().date()

        committed_points = (
            sprint.issues.filter(is_active=True).aggregate(
                total=models.Sum("story_points")
            )["total"]
            or 0
        )
        sprint.committed_points = committed_points

        sprint.save()

        LoggerService.log_info(
            action="sprint_started",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "sprint_id": str(sprint.id),
                "sprint_name": sprint.name,
                "project_id": str(sprint.project.id),
                "committed_points": float(committed_points),
            },
        )

        serializer = self.get_serializer(sprint)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sprints"],
        operation_id="sprints_complete",
        summary="Complete Sprint ",
        description="Complete a sprint. Moves incomplete issues to backlog. Calculates final metrics.",  # noqa: E501
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete_sprint(self, request, pk=None):
        from django.db import models

        sprint = self.get_object()

        if sprint.status == "completed":
            return Response(
                {"error": "Sprint is already completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        move_incomplete = request.data.get("move_incomplete_to_backlog", True)

        completed_points = (
            sprint.issues.filter(is_active=True, status__is_final=True).aggregate(
                total=models.Sum("story_points")
            )["total"]
            or 0
        )

        if move_incomplete:
            incomplete_issues = sprint.issues.filter(
                is_active=True, status__is_final=False
            )
            incomplete_issues.update(sprint=None)

        sprint.status = "completed"
        sprint.completed_points = completed_points
        sprint.completed_at = datetime.now()
        if not sprint.end_date:
            sprint.end_date = datetime.now().date()
        sprint.save()

        LoggerService.log_info(
            action="sprint_completed",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "sprint_id": str(sprint.id),
                "sprint_name": sprint.name,
                "project_id": str(sprint.project.id),
                "completed_points": float(completed_points),
                "committed_points": float(sprint.committed_points),
            },
        )

        serializer = self.get_serializer(sprint)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sprints"],
        operation_id="sprints_progress",
        summary="View Sprint Progress ",
        description="Get detailed progress metrics for the sprint.",
    )
    @action(detail=True, methods=["get"], url_path="progress")
    def progress(self, request, pk=None):
        from django.db import models

        sprint = self.get_object()

        total_issues = sprint.issues.filter(is_active=True).count()
        completed_issues = sprint.issues.filter(
            is_active=True, status__is_final=True
        ).count()

        total_points = (
            sprint.issues.filter(is_active=True).aggregate(
                total=models.Sum("story_points")
            )["total"]
            or 0
        )

        completed_points = (
            sprint.issues.filter(is_active=True, status__is_final=True).aggregate(
                total=models.Sum("story_points")
            )["total"]
            or 0
        )

        progress_data = {
            "sprint_id": str(sprint.id),
            "sprint_name": sprint.name,
            "status": sprint.status,
            "total_issues": total_issues,
            "completed_issues": completed_issues,
            "remaining_issues": total_issues - completed_issues,
            "total_story_points": float(total_points),
            "completed_story_points": float(completed_points),
            "remaining_story_points": float(total_points - completed_points),
            "completion_percentage": round(
                (completed_issues / total_issues * 100) if total_issues > 0 else 0, 2
            ),
            "points_completion_percentage": round(
                (completed_points / total_points * 100) if total_points > 0 else 0, 2
            ),
            "duration_days": sprint.duration_days,
            "remaining_days": sprint.remaining_days,
        }

        return Response(progress_data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sprints"],
        operation_id="sprints_burndown",
        summary="Get Burndown Chart Data ",
        description="Generate burndown chart data with ideal and actual lines.",
    )
    @action(detail=True, methods=["get"], url_path="burndown")
    def burndown(self, request, pk=None):
        from datetime import timedelta

        from django.db import models

        sprint = self.get_object()

        if not sprint.start_date or not sprint.end_date:
            return Response(
                {"error": "Sprint must have start and end dates"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_points = sprint.committed_points or 0
        duration = (sprint.end_date - sprint.start_date).days + 1

        ideal_line = []
        for day in range(duration + 1):
            remaining = total_points - (total_points / duration * day)
            ideal_line.append(
                {
                    "day": day,
                    "date": str(sprint.start_date + timedelta(days=day)),
                    "remaining_points": round(max(0, remaining), 2),
                }
            )

        actual_line = []
        current_date = sprint.start_date
        for day in range(duration + 1):
            if current_date <= datetime.now().date():
                completed = (
                    sprint.issues.filter(
                        is_active=True,
                        status__is_final=True,
                        resolved_at__date__lte=current_date,
                    ).aggregate(total=models.Sum("story_points"))["total"]
                    or 0
                )
                remaining = max(0, total_points - completed)
            else:
                remaining = None

            actual_line.append(
                {
                    "day": day,
                    "date": str(current_date),
                    "remaining_points": (
                        round(remaining, 2) if remaining is not None else None
                    ),
                }
            )
            current_date += timedelta(days=1)

        burndown_data = {
            "sprint_id": str(sprint.id),
            "sprint_name": sprint.name,
            "start_date": str(sprint.start_date),
            "end_date": str(sprint.end_date),
            "total_points": float(total_points),
            "ideal_line": ideal_line,
            "actual_line": actual_line,
        }

        return Response(burndown_data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sprints"],
        operation_id="sprints_add_issue",
        summary="Add Issue to Sprint",
        description="Add an issue to the sprint. Requires issue_id in request body.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "issue_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the issue to add to sprint",
                    }
                },
                "required": ["issue_id"],
                "example": {"issue_id": "123e4567-e89b-12d3-a456-426614174000"},
            }
        },
        responses={
            200: {
                "description": "Issue added successfully",
                "content": {
                    "application/json": {
                        "example": {"message": "Issue added to sprint successfully"}
                    }
                },
            },
            400: {
                "description": "Bad request - missing issue_id, wrong project, or sprint completed",  # noqa: E501
                "content": {
                    "application/json": {
                        "examples": {
                            "missing_id": {"value": {"error": "issue_id is required"}},
                            "wrong_project": {
                                "value": {
                                    "error": "Issue does not belong to this project"
                                }
                            },
                            "completed": {
                                "value": {
                                    "error": "Cannot add issues to a completed sprint"
                                }
                            },
                        }
                    }
                },
            },
            404: {
                "description": "Issue not found",
                "content": {
                    "application/json": {"example": {"error": "Issue does not exist"}}
                },
            },
        },
    )
    @action(detail=True, methods=["post"], url_path="issues")
    def add_issue(self, request, pk=None):
        from apps.projects.models import Issue

        sprint = self.get_object()

        if sprint.status == "completed":
            return Response(
                {"error": "Cannot add issues to a completed sprint"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue_id = request.data.get("issue_id")
        if not issue_id:
            return Response(
                {"error": "issue_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            issue = Issue.objects.get(id=issue_id)
        except Issue.DoesNotExist:
            return Response(
                {"error": "Issue does not exist"}, status=status.HTTP_404_NOT_FOUND
            )

        if issue.project != sprint.project:
            return Response(
                {"error": "Issue does not belong to this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue.sprint = sprint
        issue.save()

        LoggerService.log_info(
            action="issue_added_to_sprint",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "sprint_id": str(sprint.id),
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
            },
        )

        return Response(
            {"message": "Issue added to sprint successfully"}, status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=["Sprints"],
        operation_id="sprints_remove_issue",
        summary="Remove Issue from Sprint",
        description="Remove an issue from the sprint.",
    )
    @action(detail=True, methods=["delete"], url_path="issues/(?P<issue_id>[^/.]+)")
    def remove_issue(self, request, pk=None, issue_id=None):
        from apps.projects.models import Issue

        sprint = self.get_object()

        try:
            issue = Issue.objects.get(id=issue_id, sprint=sprint)
        except Issue.DoesNotExist:
            return Response(
                {"error": "Issue not found in this sprint"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if sprint.status == "completed":
            return Response(
                {"error": "Cannot remove issues from a completed sprint"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue.sprint = None
        issue.save()

        LoggerService.log_info(
            action="issue_removed_from_sprint",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "sprint_id": str(sprint.id),
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
            },
        )

        return Response(
            {"message": "Issue removed from sprint successfully"},
            status=status.HTTP_200_OK,
        )
