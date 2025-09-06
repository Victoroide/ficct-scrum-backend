from rest_framework import serializers
from django.db import transaction
from apps.logging.models import AlertRule
from apps.authentication.serializers import UserSerializer


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
