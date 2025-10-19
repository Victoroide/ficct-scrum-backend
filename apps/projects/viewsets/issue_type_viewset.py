from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.projects.models import IssueType
from apps.projects.permissions import CanAccessProject
from apps.projects.serializers.issue_type_serializer import (
    IssueTypeListSerializer,
    IssueTypeSerializer,
)


class IssueTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for IssueType model.
    
    Provides list and retrieve actions for issue types.
    Issue types are read-only through the API as they should be managed
    through project configuration.
    
    Filters:
    - By default, returns issue types for projects the user has access to
    - Use ?project=<project_id> to filter by specific project
    """

    permission_classes = [IsAuthenticated, CanAccessProject]

    def get_serializer_class(self):
        if self.action == "list":
            return IssueTypeListSerializer
        return IssueTypeSerializer

    def get_queryset(self):
        user = self.request.user

        # Base queryset - only active issue types
        queryset = IssueType.objects.filter(is_active=True).select_related("project")

        # Filter by project if specified
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project__id=project_id)

        # User can see issue types from projects they have access to
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

        return queryset.order_by("project", "name")
