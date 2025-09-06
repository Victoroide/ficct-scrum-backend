from rest_framework import serializers
from django.db import transaction
from apps.logging.models import SystemLog, ErrorLog, AuditLog, AlertRule, Alert
from apps.authentication.serializers import UserSerializer


class SystemLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = SystemLog
        fields = [
            'id', 'level', 'action', 'action_type', 'message', 'user',
            'ip_address', 'user_agent', 'request_method', 'request_path',
            'request_data', 'response_status', 'execution_time', 'metadata',
            'stack_trace', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ErrorLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)

    class Meta:
        model = ErrorLog
        fields = [
            'id', 'error_type', 'error_message', 'stack_trace', 'severity',
            'status', 'user', 'ip_address', 'request_data', 'environment_info',
            'occurrence_count', 'first_occurrence', 'last_occurrence',
            'resolved_by', 'resolved_at', 'resolution_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'ip_address', 'request_data', 'environment_info',
            'occurrence_count', 'first_occurrence', 'last_occurrence',
            'created_at', 'updated_at'
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'action', 'resource_type', 'resource_id',
            'old_values', 'new_values', 'ip_address', 'user_agent',
            'session_id', 'additional_data', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AlertRuleSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'description', 'condition_type', 'condition_config',
            'severity', 'status', 'notification_channels', 'created_by',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        return AlertRule.objects.create(**validated_data)


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


class SystemHealthSerializer(serializers.Serializer):
    total_logs_24h = serializers.IntegerField()
    error_logs_24h = serializers.IntegerField()
    error_logs_1h = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    critical_errors_24h = serializers.IntegerField()
    unique_users_24h = serializers.IntegerField()
