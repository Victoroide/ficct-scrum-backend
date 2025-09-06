from rest_framework import serializers
from apps.logging.models import AuditLog
from apps.authentication.serializers import UserSerializer


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
