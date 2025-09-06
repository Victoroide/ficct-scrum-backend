from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.logging.models import SystemLog
from apps.logging.serializers import SystemLogSerializer, SystemHealthSerializer
from apps.logging.services import LoggerService


@extend_schema(tags=['Logs: System'])
class SystemLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SystemLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['level', 'action_type', 'user']
    search_fields = ['action', 'message']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return SystemLog.objects.select_related('user').all()

    @extend_schema(responses={200: SystemHealthSerializer})
    @action(detail=False, methods=['get'])
    def health_metrics(self, request):
        try:
            metrics = LoggerService.get_system_health_metrics()
            serializer = SystemHealthSerializer(metrics)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            LoggerService.log_error(
                action='get_health_metrics_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to retrieve health metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
