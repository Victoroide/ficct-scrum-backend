from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from apps.logging.models import SystemLog, ErrorLog, AuditLog, AlertRule, Alert
from apps.logging.serializers import (
    SystemLogSerializer,
    ErrorLogSerializer,
    AuditLogSerializer,
    AlertRuleSerializer,
    AlertSerializer,
    SystemHealthSerializer
)
from apps.logging.services import LoggerService


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


class ErrorLogViewSet(viewsets.ModelViewSet):
    serializer_class = ErrorLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['severity', 'status', 'error_type']
    search_fields = ['error_message', 'error_type']
    ordering = ['-last_occurrence']
    
    def get_queryset(self):
        return ErrorLog.objects.select_related('user', 'resolved_by').all()

    @extend_schema(
        request={'resolution_notes': 'string'},
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


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['action', 'resource_type', 'user']
    search_fields = ['resource_type', 'resource_id']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return AuditLog.objects.select_related('user').all()


class AlertRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AlertRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['condition_type', 'severity', 'status']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def get_queryset(self):
        return AlertRule.objects.select_related('created_by').all()

    @extend_schema(responses={200: AlertRuleSerializer})
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def activate(self, request, pk=None):
        try:
            alert_rule = self.get_object()
            alert_rule.status = 'active'
            alert_rule.is_active = True
            alert_rule.save()
            
            LoggerService.log_info(
                action='alert_rule_activated',
                user=request.user,
                details={'alert_rule_id': str(alert_rule.id)}
            )
            
            serializer = self.get_serializer(alert_rule)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='activate_alert_rule_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to activate alert rule'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(responses={200: AlertRuleSerializer})
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def deactivate(self, request, pk=None):
        try:
            alert_rule = self.get_object()
            alert_rule.status = 'inactive'
            alert_rule.is_active = False
            alert_rule.save()
            
            LoggerService.log_info(
                action='alert_rule_deactivated',
                user=request.user,
                details={'alert_rule_id': str(alert_rule.id)}
            )
            
            serializer = self.get_serializer(alert_rule)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='deactivate_alert_rule_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to deactivate alert rule'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
