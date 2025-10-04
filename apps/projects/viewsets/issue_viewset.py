from datetime import datetime

from django.db import transaction
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Issue, WorkflowStatus
from apps.projects.permissions import (
    CanAccessProject,
    CanDeleteIssue,
    CanModifyIssue,
    IsProjectTeamMember,
)
from apps.projects.serializers import (
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueListSerializer,
    IssueUpdateSerializer,
)
from apps.projects.services import WorkflowValidator


class IssueFilter(filters.FilterSet):
    project = filters.UUIDFilter(field_name="project__id")
    sprint = filters.UUIDFilter(field_name="sprint__id")
    assignee = filters.UUIDFilter(field_name="assignee__id")
    reporter = filters.UUIDFilter(field_name="reporter__id")
    status = filters.UUIDFilter(field_name="status__id")
    issue_type = filters.UUIDFilter(field_name="issue_type__id")
    priority = filters.ChoiceFilter(choices=Issue.PRIORITY_CHOICES)
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Issue
        fields = ["project", "sprint", "assignee", "reporter", "status", "issue_type", "priority"]

    def filter_search(self, queryset, name, value):
        from django.db import models as django_models
        return queryset.filter(
            django_models.Q(title__icontains=value) |
            django_models.Q(description__icontains=value) |
            django_models.Q(key__icontains=value)
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Issues"],
        operation_id="issues_list",
        summary="List Issues",
        description="Get all issues with filtering by project, sprint, assignee, status, priority, etc.",
    ),
    retrieve=extend_schema(
        tags=["Issues"],
        operation_id="issues_retrieve",
        summary="Get Issue Details",
    ),
    create=extend_schema(
        tags=["Issues"],
        operation_id="issues_create",
        summary="Create Issue (UC-024 to UC-027)",
        description="Create Epic, User Story, Task, or Bug. Issue key is auto-generated. Initial status is set to project's default.",
    ),
    update=extend_schema(
        tags=["Issues"],
        operation_id="issues_update",
        summary="Update Issue (UC-028)",
    ),
    partial_update=extend_schema(
        tags=["Issues"],
        operation_id="issues_partial_update",
        summary="Partial Update Issue",
    ),
    destroy=extend_schema(
        tags=["Issues"],
        operation_id="issues_destroy",
        summary="Delete Issue",
    ),
)
class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_class = IssueFilter
    ordering_fields = ["priority", "created_at", "updated_at", "order"]
    ordering = ["-created_at"]

    def get_queryset(self):
        from django.db.models import Q

        return Issue.objects.filter(
            Q(project__workspace__members__user=self.request.user,
              project__workspace__members__is_active=True) |
            Q(project__team_members__user=self.request.user,
              project__team_members__is_active=True)
        ).select_related(
            "project",
            "issue_type",
            "status",
            "assignee",
            "reporter",
            "sprint",
            "parent_issue"
        ).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return IssueCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return IssueUpdateSerializer
        elif self.action == "retrieve":
            return IssueDetailSerializer
        return IssueListSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsProjectTeamMember()]
        elif self.action in ["update", "partial_update"]:
            return [IsAuthenticated(), CanModifyIssue()]
        elif self.action == "destroy":
            return [IsAuthenticated(), CanDeleteIssue()]
        elif self.action in ["retrieve", "list"]:
            return [IsAuthenticated(), CanAccessProject()]
        return [IsAuthenticated()]

    @transaction.atomic
    def perform_create(self, serializer):
        issue = serializer.save()

        LoggerService.log_info(
            action="issue_created",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
                "issue_type": issue.issue_type.category,
                "project_id": str(issue.project.id),
            },
        )

    @transaction.atomic
    def perform_update(self, serializer):
        issue = serializer.save()

        LoggerService.log_info(
            action="issue_updated",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
            },
        )

    @extend_schema(
        tags=["Issues"],
        operation_id="issues_assign",
        summary="Assign Issue to User (UC-029)",
        description="Assign or reassign issue to a project team member.",
    )
    @action(detail=True, methods=["patch"], url_path="assign")
    def assign(self, request, pk=None):
        from apps.authentication.models import User

        issue = self.get_object()
        assignee_id = request.data.get("assignee")

        if not assignee_id:
            issue.assignee = None
            issue.save()
            return Response(
                {"message": "Issue unassigned successfully"},
                status=status.HTTP_200_OK
            )

        try:
            assignee = User.objects.get(id=assignee_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Assignee user does not exist"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.projects.models import ProjectTeamMember

        if not ProjectTeamMember.objects.filter(
            project=issue.project, user=assignee, is_active=True
        ).exists():
            return Response(
                {"error": "Assignee is not a member of this project"},
                status=status.HTTP_400_BAD_REQUEST
            )

        issue.assignee = assignee
        issue.save()

        LoggerService.log_info(
            action="issue_assigned",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
                "assignee_id": str(assignee.id),
            },
        )

        serializer = self.get_serializer(issue)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Issues"],
        operation_id="issues_transition",
        summary="Change Issue Status (UC-030)",
        description="Transition issue to a new status. Validates workflow transitions.",
    )
    @action(detail=True, methods=["patch"], url_path="transition")
    def transition(self, request, pk=None):
        issue = self.get_object()
        status_id = request.data.get("status")

        if not status_id:
            return Response(
                {"error": "Status ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_status = WorkflowStatus.objects.get(id=status_id)
        except WorkflowStatus.DoesNotExist:
            return Response(
                {"error": "Status does not exist"},
                status=status.HTTP_400_BAD_REQUEST
            )

        can_transition, message = WorkflowValidator.can_transition(issue, new_status)

        if not can_transition:
            return Response(
                {"error": message},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = issue.status
        issue.status = new_status

        if new_status.is_final and not issue.resolved_at:
            issue.resolved_at = datetime.now()

        issue.save()

        LoggerService.log_info(
            action="issue_status_changed",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
                "old_status": old_status.name,
                "new_status": new_status.name,
            },
        )

        serializer = self.get_serializer(issue)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Issues"],
        operation_id="issues_set_priority",
        summary="Set Issue Priority (UC-031)",
        description="Update issue priority level.",
    )
    @action(detail=True, methods=["patch"], url_path="priority")
    def set_priority(self, request, pk=None):
        issue = self.get_object()
        priority = request.data.get("priority")

        if not priority:
            return Response(
                {"error": "Priority is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_priorities = [choice[0] for choice in Issue.PRIORITY_CHOICES]
        if priority not in valid_priorities:
            return Response(
                {"error": f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_priority = issue.priority
        issue.priority = priority
        issue.save()

        LoggerService.log_info(
            action="issue_priority_changed",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
                "old_priority": old_priority,
                "new_priority": priority,
            },
        )

        serializer = self.get_serializer(issue)
        return Response(serializer.data, status=status.HTTP_200_OK)
