from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils import timezone
from apps.logging.models import ErrorLog
from apps.logging.serializers import ErrorLogSerializer


@extend_schema_view(
    list=extend_schema(tags=['Logging'], operation_id='error_logs_list', summary='List Error Logs'),
    retrieve=extend_schema(tags=['Logging'], operation_id='error_logs_retrieve', summary='Get Error Log Details'),
    update=extend_schema(tags=['Logging'], operation_id='error_logs_update', summary='Update Error Log'),
    partial_update=extend_schema(tags=['Logging'], operation_id='error_logs_partial_update', summary='Partial Update Error Log'),
)
class ErrorLogViewSet(viewsets.ModelViewSet):
    queryset = ErrorLog.objects.all()
    serializer_class = ErrorLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['severity', 'status', 'error_type']
    search_fields = ['error_message', 'error_type']
    ordering = ['-last_occurrence']
    http_method_names = ['get', 'put', 'patch']

    @extend_schema(tags=['Logging'], operation_id='error_logs_resolve', summary='Resolve Error Log')
    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        error_log = self.get_object()
        resolution_notes = request.data.get('resolution_notes', '')
        
        error_log.status = 'resolved'
        error_log.resolved_by = request.user
        error_log.resolved_at = timezone.now()
        error_log.resolution_notes = resolution_notes
        error_log.save()
        
        serializer = self.get_serializer(error_log)
        return Response(serializer.data, status=status.HTTP_200_OK)
