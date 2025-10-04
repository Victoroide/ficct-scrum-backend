from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from apps.logging.models import SystemLog
from apps.logging.serializers import SystemLogSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Logging"],
        operation_id="system_logs_list",
        summary="List System Logs",
        description="Retrieve system logs with filtering and search capabilities. Admin access required.",
    ),
    retrieve=extend_schema(
        tags=["Logging"],
        operation_id="system_logs_retrieve",
        summary="Get System Log Details",
        description="Retrieve detailed information about a specific system log entry.",
    ),
)
class SystemLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemLog.objects.all()
    serializer_class = SystemLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filterset_fields = ["level", "action_type", "user", "ip_address"]
    search_fields = ["action", "message", "user__email"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.exclude(level="DEBUG")
        return queryset
