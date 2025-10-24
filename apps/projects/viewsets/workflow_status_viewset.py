from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.projects.models import WorkflowStatus
from apps.projects.permissions import CanAccessProject
from apps.projects.serializers.workflow_status_serializer import (
    WorkflowStatusListSerializer,
    WorkflowStatusSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Workflow"],
        operation_id="workflow_statuses_list",
        summary="List Workflow Statuses",
        description="List available workflow statuses for projects user has access to. Filter by project UUID to get statuses for issue dropdowns and board columns.",
    ),
    retrieve=extend_schema(
        tags=["Workflow"],
        operation_id="workflow_statuses_retrieve",
        summary="Get Workflow Status Details",
    ),
)
class WorkflowStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for WorkflowStatus model.
    
    Provides list and retrieve actions for workflow statuses.
    Workflow statuses define the possible states an issue can be in (e.g., To Do, In Progress, Done).
    
    Filters:
    - By default, returns workflow statuses for projects the user has access to
    - Use ?project=<project_id> to filter by specific project (required for most use cases)
    
    Usage:
    - GET /api/v1/projects/workflow-statuses/?project={uuid} - Get statuses for a specific project
    - Used to populate issue status dropdowns and board columns
    """

    permission_classes = [IsAuthenticated, CanAccessProject]

    def get_serializer_class(self):
        if self.action == "list":
            return WorkflowStatusListSerializer
        return WorkflowStatusSerializer

    def get_queryset(self):
        user = self.request.user

        # Base queryset - only active workflow statuses
        queryset = WorkflowStatus.objects.filter(is_active=True).select_related("project")

        # Filter by project if specified
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project__id=project_id)

        # User can see workflow statuses from projects they have access to
        # Through project membership OR workspace membership
        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        accessible_projects = Q(
            project__team_members__user=user, project__team_members__is_active=True
        ) | Q(
            project__workspace__members__user=user,
            project__workspace__members__is_active=True,
        )

        queryset = queryset.filter(accessible_projects).distinct()

        return queryset.order_by("project", "order", "name")
