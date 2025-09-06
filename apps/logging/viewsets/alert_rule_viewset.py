from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from drf_spectacular.utils import extend_schema

from apps.logging.models import AlertRule
from apps.logging.serializers import AlertRuleSerializer
from apps.logging.services import LoggerService


@extend_schema(tags=['Logs: Alert Rules'])
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
