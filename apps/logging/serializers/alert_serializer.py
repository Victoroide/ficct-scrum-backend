from rest_framework import serializers
from apps.logging.models import Alert
from apps.authentication.serializers import UserSerializer
from .alert_rule_serializer import AlertRuleSerializer


class AlertSerializer(serializers.ModelSerializer):
    rule = AlertRuleSerializer(read_only=True)
    acknowledged_by = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'rule', 'status', 'message', 'details', 'triggered_at',
            'acknowledged_at', 'acknowledged_by', 'resolved_at', 'resolved_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'rule', 'message', 'details', 'triggered_at',
            'acknowledged_at', 'acknowledged_by', 'resolved_at', 'resolved_by',
            'created_at', 'updated_at'
        ]
