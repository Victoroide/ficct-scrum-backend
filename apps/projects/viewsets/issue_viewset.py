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
    board = filters.UUIDFilter(method="filter_board")
    assignee = filters.UUIDFilter(field_name="assignee__id")
    reporter = filters.UUIDFilter(field_name="reporter__id")
    status = filters.UUIDFilter(field_name="status__id")
    issue_type = filters.UUIDFilter(field_name="issue_type__id")
    priority = filters.ChoiceFilter(choices=Issue.PRIORITY_CHOICES)
    search = filters.CharFilter(method="filter_search")
    
    has_attachments = filters.BooleanFilter(method="filter_has_attachments")
    has_comments = filters.BooleanFilter(method="filter_has_comments")
    has_links = filters.BooleanFilter(method="filter_has_links")
    
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    updated_after = filters.DateTimeFilter(field_name="updated_at", lookup_expr="gte")
    updated_before = filters.DateTimeFilter(field_name="updated_at", lookup_expr="lte")
    resolved_after = filters.DateTimeFilter(field_name="resolved_at", lookup_expr="gte")
    resolved_before = filters.DateTimeFilter(field_name="resolved_at", lookup_expr="lte")

    class Meta:
        model = Issue
        fields = ["project", "sprint", "board", "assignee", "reporter", "status", "issue_type", "priority"]

    def filter_search(self, queryset, name, value):
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
        from django.db import models as django_models
        
        try:
            search_vector = SearchVector("title", weight="A") + SearchVector("description", weight="B") + SearchVector("key", weight="A")
            search_query = SearchQuery(value)
            
            return queryset.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).order_by("-rank")
        except Exception:
            return queryset.filter(
                django_models.Q(title__icontains=value) |
                django_models.Q(description__icontains=value) |
                django_models.Q(key__icontains=value)
            )
    
    def filter_has_attachments(self, queryset, name, value):
        if value:
            return queryset.filter(attachments__isnull=False).distinct()
        return queryset.filter(attachments__isnull=True)
    
    def filter_has_comments(self, queryset, name, value):
        if value:
            return queryset.filter(comments__isnull=False).distinct()
        return queryset.filter(comments__isnull=True)
    
    def filter_has_links(self, queryset, name, value):
        from django.db import models as django_models
        if value:
            return queryset.filter(
                django_models.Q(source_links__isnull=False) | django_models.Q(target_links__isnull=False)
            ).distinct()
        return queryset.filter(source_links__isnull=True, target_links__isnull=True)
    
    def filter_board(self, queryset, name, value):
        from apps.projects.models import Board
        try:
            board = Board.objects.get(id=value)
            # Return ALL active issues from the board's project (Board as a View, not a container)
            filtered_queryset = queryset.filter(project=board.project, is_active=True)
            
            # Apply saved_filter from board if exists
            if board.saved_filter:
                # Apply additional filters from board configuration
                if 'priority' in board.saved_filter:
                    filtered_queryset = filtered_queryset.filter(priority__in=board.saved_filter['priority'])
                if 'assignee' in board.saved_filter:
                    filtered_queryset = filtered_queryset.filter(assignee__id__in=board.saved_filter['assignee'])
                if 'issue_type' in board.saved_filter:
                    filtered_queryset = filtered_queryset.filter(issue_type__id__in=board.saved_filter['issue_type'])
            
            return filtered_queryset
        except Board.DoesNotExist:
            return queryset.none()


@extend_schema_view(
    list=extend_schema(
        tags=["Issues"],
        operation_id="issues_list",
        summary="List Issues",
        description="Get all issues with filtering by project, sprint, board, assignee, status, priority, etc. Use board filter to get issues displayed in a specific Kanban board.",
    ),
    retrieve=extend_schema(
        tags=["Issues"],
        operation_id="issues_retrieve",
        summary="Get Issue Details",
    ),
    create=extend_schema(
        tags=["Issues"],
        operation_id="issues_create",
        summary="Create Issue",
        description="Create Epic, User Story, Task, or Bug. Issue key is auto-generated. Initial status is set to project's default.",
    ),
    update=extend_schema(
        tags=["Issues"],
        operation_id="issues_update",
        summary="Update Issue ",
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
    
    def update(self, request, *args, **kwargs):
        """
        Override update to return detailed serializer with expanded relations.
        Uses IssueUpdateSerializer for validation but IssueDetailSerializer for response.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        # Return with detailed serializer (expanded relations)
        response_serializer = IssueDetailSerializer(instance, context=self.get_serializer_context())
        return Response(response_serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """
        Override partial_update to return detailed serializer with expanded relations.
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(
        tags=["Issues"],
        operation_id="issues_assign",
        summary="Assign Issue to User ",
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

        # Return with detailed serializer (expanded relations)
        serializer = IssueDetailSerializer(issue, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Issues"],
        operation_id="issues_transition",
        summary="Change Issue Status ",
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

        # Return with detailed serializer (expanded relations)
        serializer = IssueDetailSerializer(issue, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Issues"],
        operation_id="issues_set_priority",
        summary="Set Issue Priority ",
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

        # Return with detailed serializer (expanded relations)
        serializer = IssueDetailSerializer(issue, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)
