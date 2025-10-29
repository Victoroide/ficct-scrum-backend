from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.reporting.models import ActivityLog
from apps.reporting.serializers import ActivityLogSerializer


class ActivityLogFilter(filters.FilterSet):
    """
    Flexible filtering for activity logs supporting multiple filter types.
    
    Supports both UUID-based and user-friendly filters:
    - project (UUID) or project_key (string) - Filter by project
    - workspace (UUID) or workspace_key (string) - Filter by workspace  
    - organization (UUID) - Filter by organization
    - user (UUID) or user_email (string) - Filter by user who performed action
    - action_type - Filter by action type (created, updated, deleted, etc.)
    - object_type - Filter by content type (issue, sprint, board, etc.)
    
    Examples:
    - /api/v1/reporting/activity-logs/?project_key=FICCT
    - /api/v1/reporting/activity-logs/?workspace_key=SCRUM
    - /api/v1/reporting/activity-logs/?action_type=created
    - /api/v1/reporting/activity-logs/?user_email=user@example.com
    - /api/v1/reporting/activity-logs/?created_after=2024-01-01
    """
    # UUID-based filters
    project = filters.UUIDFilter(field_name="project__id")
    workspace = filters.UUIDFilter(field_name="workspace__id")
    organization = filters.UUIDFilter(field_name="organization__id")
    user = filters.UUIDFilter(field_name="user__id")
    
    # User-friendly alternative filters
    project_key = filters.CharFilter(field_name="project__key", lookup_expr="iexact")
    workspace_key = filters.CharFilter(field_name="workspace__key", lookup_expr="iexact")
    user_email = filters.CharFilter(field_name="user__email", lookup_expr="iexact")
    
    # Action filters
    action_type = filters.ChoiceFilter(choices=ActivityLog.ACTION_TYPE_CHOICES)
    object_type = filters.CharFilter(method="filter_object_type")
    
    # Date range filters
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    
    class Meta:
        model = ActivityLog
        fields = [
            "project", "workspace", "organization", "user",
            "project_key", "workspace_key", "user_email",
            "action_type", "object_type"
        ]
    
    def filter_object_type(self, queryset, name, value):
        """
        Filter by content type model name (e.g., 'issue', 'sprint', 'board').
        Case-insensitive match.
        """
        from django.contrib.contenttypes.models import ContentType
        try:
            content_type = ContentType.objects.get(model=value.lower())
            return queryset.filter(content_type=content_type)
        except ContentType.DoesNotExist:
            return queryset.none()


@extend_schema_view(
    list=extend_schema(
        tags=["Reporting"],
        operation_id="activity_logs_list",
        summary="List Activity Logs",
        description=(
            "Get activity history with flexible filtering options. Similar to Jira's Activity Stream.\n\n"
            "**Filter by Scope:**\n"
            "- Organization: `?organization=<uuid>` - All activity in organization\n"
            "- Workspace: `?workspace=<uuid>` or `?workspace_key=SCRUM` - All activity in workspace\n"
            "- Project: `?project=<uuid>` or `?project_key=FICCT` - All activity in project\n\n"
            "**Filter by Action:**\n"
            "- Action type: `?action_type=created` (created, updated, deleted, transitioned, etc.)\n"
            "- Object type: `?object_type=issue` (issue, sprint, board, etc.)\n"
            "- User: `?user=<uuid>` or `?user_email=user@example.com`\n\n"
            "**Filter by Time:**\n"
            "- Recent: `?created_after=2024-01-01T00:00:00Z`\n"
            "- Range: `?created_after=2024-01-01&created_before=2024-12-31`\n\n"
            "**Combine Filters:**\n"
            "- `?project_key=FICCT&action_type=transitioned&created_after=2024-01-01`\n"
            "- `?workspace_key=SCRUM&user_email=user@example.com&object_type=issue`"
        ),
        parameters=[
            OpenApiParameter(
                name="organization",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by organization UUID"
            ),
            OpenApiParameter(
                name="workspace",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by workspace UUID"
            ),
            OpenApiParameter(
                name="workspace_key",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by workspace key (e.g., 'SCRUM'). Case-insensitive."
            ),
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by project UUID"
            ),
            OpenApiParameter(
                name="project_key",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by project key (e.g., 'FICCT'). Case-insensitive."
            ),
            OpenApiParameter(
                name="user",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by user UUID who performed the action"
            ),
            OpenApiParameter(
                name="user_email",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by user email. Case-insensitive."
            ),
            OpenApiParameter(
                name="action_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by action type (created, updated, deleted, transitioned, commented, etc.)"
            ),
            OpenApiParameter(
                name="object_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by object type (issue, sprint, board, project, etc.)"
            ),
            OpenApiParameter(
                name="created_after",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter activities created after this datetime (ISO 8601 format)"
            ),
            OpenApiParameter(
                name="created_before",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter activities created before this datetime (ISO 8601 format)"
            ),
        ]
    ),
    retrieve=extend_schema(
        tags=["Reporting"],
        operation_id="activity_logs_retrieve",
        summary="Get Activity Log Details",
        description="Get detailed information about a specific activity log entry."
    ),
)
class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Activity Logs - Similar to Jira's Activity Stream.
    
    Provides complete activity history across organization, workspace, and project levels.
    Supports flexible filtering by scope, action type, user, object type, and time range.
    
    **Access Control:**
    - Users can only see activity logs from organizations/workspaces/projects they have access to
    - Filtering is automatic based on user permissions
    
    **Use Cases:**
    - Organization dashboard: All activity across all workspaces/projects
    - Workspace dashboard: All activity in workspace projects
    - Project dashboard: All activity in specific project
    - User profile: All activity by specific user
    - Audit trail: Filter by action type and time range
    """
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = ActivityLogFilter
    ordering_fields = ["created_at", "action_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Get activity logs filtered by user access permissions.
        
        Users can only see logs from:
        - Organizations they are members of
        - Workspaces they are members of
        - Projects they are members of (directly or via workspace)
        """
        from django.db.models import Q
        
        user = self.request.user
        
        # Get all accessible logs based on user memberships
        # Note: organization.memberships (not members), workspace.members, project.team_members
        queryset = ActivityLog.objects.filter(
            Q(organization__memberships__user=user, organization__memberships__is_active=True) |
            Q(workspace__members__user=user, workspace__members__is_active=True) |
            Q(project__workspace__members__user=user, project__workspace__members__is_active=True) |
            Q(project__team_members__user=user, project__team_members__is_active=True)
        ).select_related(
            "user",
            "project",
            "project__workspace",
            "workspace",
            "workspace__organization",
            "organization",
            "content_type"
        ).distinct()
        
        return queryset
