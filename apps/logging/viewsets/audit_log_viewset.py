from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema

from apps.logging.models import AuditLog
from apps.logging.serializers import AuditLogSerializer


@extend_schema(tags=['Logs: Audit'])
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['action', 'resource_type', 'user']
    search_fields = ['resource_type', 'resource_id']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return AuditLog.objects.select_related('user').all()
