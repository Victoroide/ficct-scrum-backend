from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.logging.models import ErrorLog
from apps.logging.serializers import ErrorLogSerializer
from apps.logging.services import LoggerService


class ErrorLogViewSet(viewsets.ModelViewSet):
    serializer_class = ErrorLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['severity', 'status', 'error_type']
    search_fields = ['error_message', 'error_type']
    ordering = ['-last_occurrence']
    
    def get_queryset(self):
        return ErrorLog.objects.select_related('user', 'resolved_by').all()

    @extend_schema(
        request=inline_serializer(
            name='ResolveErrorLogRequest',
            fields={'resolution_notes': serializers.CharField(required=False)}
        ),
        responses={200: ErrorLogSerializer}
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def resolve(self, request, pk=None):
        try:
            error_log = self.get_object()
            resolution_notes = request.data.get('resolution_notes', '')
            
            error_log.status = 'resolved'
            error_log.resolved_by = request.user
            error_log.resolved_at = timezone.now()
            error_log.resolution_notes = resolution_notes
            error_log.save()
            
            LoggerService.log_info(
                action='error_log_resolved',
                user=request.user,
                details={
                    'error_log_id': str(error_log.id),
                    'error_type': error_log.error_type
                }
            )
            
            serializer = self.get_serializer(error_log)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='resolve_error_log_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to resolve error log'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
