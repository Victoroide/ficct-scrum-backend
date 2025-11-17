from django.db.models import Q
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.reporting.models import SavedFilter
from apps.reporting.permissions import CanGenerateReports
from apps.reporting.serializers import SavedFilterSerializer


@extend_schema_view(
    list=extend_schema(summary="List saved filters", tags=["Reporting"]),
    retrieve=extend_schema(summary="Get filter details", tags=["Reporting"]),
    create=extend_schema(summary="Create saved filter", tags=["Reporting"]),
    update=extend_schema(summary="Update saved filter", tags=["Reporting"]),
    partial_update=extend_schema(
        summary="Partially update saved filter", tags=["Reporting"]
    ),
    destroy=extend_schema(summary="Delete saved filter", tags=["Reporting"]),
)
class SavedFilterViewSet(viewsets.ModelViewSet):
    queryset = SavedFilter.objects.all()
    serializer_class = SavedFilterSerializer
    permission_classes = [CanGenerateReports]

    def get_queryset(self):
        queryset = SavedFilter.objects.all()

        user = self.request.user
        project_id = self.request.query_params.get("project")

        if project_id:
            queryset = queryset.filter(project_id=project_id).filter(
                Q(user=user) | Q(is_public=True) | Q(shared_with_team=True)
            )
        else:
            queryset = queryset.filter(user=user)

        return queryset.select_related("user", "project")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.user != self.request.user:
            raise PermissionError("You can only update your own filters")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionError("You can only delete your own filters")
        instance.delete()

    @extend_schema(
        summary="Apply filter to get issues",
        tags=["Reporting"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        saved_filter = self.get_object()

        saved_filter.use_count += 1
        saved_filter.last_used_at = timezone.now()
        saved_filter.save(update_fields=["use_count", "last_used_at"])

        from apps.projects.models import Issue
        from apps.projects.serializers.issue_serializer import IssueListSerializer

        issues = Issue.objects.filter(project=saved_filter.project, is_active=True)

        criteria = saved_filter.filter_criteria
        if criteria.get("status"):
            issues = issues.filter(status_id=criteria["status"])
        if criteria.get("assignee"):
            issues = issues.filter(assignee_id=criteria["assignee"])
        if criteria.get("priority"):
            issues = issues.filter(priority=criteria["priority"])
        if criteria.get("issue_type"):
            issues = issues.filter(issue_type_id=criteria["issue_type"])
        if criteria.get("sprint"):
            issues = issues.filter(sprint_id=criteria["sprint"])

        serializer = IssueListSerializer(issues[:100], many=True)
        return Response(
            {
                "filter": SavedFilterSerializer(saved_filter).data,
                "issues": serializer.data,
                "total_count": issues.count(),
            },
            status=status.HTTP_200_OK,
        )
