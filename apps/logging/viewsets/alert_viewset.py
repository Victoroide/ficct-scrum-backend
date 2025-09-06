from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from apps.logging.models import Alert
from apps.logging.serializers import AlertSerializer
from apps.logging.services import LoggerService


@extend_schema(tags=['Logs: Alerts'])
class AlertViewSet(viewsets.ModelViewSet):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status', 'rule']
    search_fields = ['message']
    ordering = ['-triggered_at']
    
    def get_queryset(self):
        return Alert.objects.select_related('rule', 'acknowledged_by', 'resolved_by').all()

    @extend_schema(responses={200: AlertSerializer})
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def acknowledge(self, request, pk=None):
        try:
            alert = self.get_object()
            
            if alert.status != 'triggered':
                return Response(
                    {'error': 'Alert is not in triggered state'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            alert.status = 'acknowledged'
            alert.acknowledged_by = request.user
            alert.acknowledged_at = timezone.now()
            alert.save()
            
            LoggerService.log_info(
                action='alert_acknowledged',
                user=request.user,
                details={'alert_id': str(alert.id)}
            )
            
            serializer = self.get_serializer(alert)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='acknowledge_alert_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to acknowledge alert'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(responses={200: AlertSerializer})
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def resolve(self, request, pk=None):
        try:
            alert = self.get_object()
            
            if alert.status not in ['triggered', 'acknowledged']:
                return Response(
                    {'error': 'Alert cannot be resolved from current state'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            alert.status = 'resolved'
            alert.resolved_by = request.user
            alert.resolved_at = timezone.now()
            alert.save()
            
            LoggerService.log_info(
                action='alert_resolved',
                user=request.user,
                details={'alert_id': str(alert.id)}
            )
            
            serializer = self.get_serializer(alert)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='resolve_alert_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to resolve alert'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
