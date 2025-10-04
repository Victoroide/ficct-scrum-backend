from rest_framework import serializers

from apps.authentication.serializers import UserSerializer
from apps.logging.models import SystemLog


class SystemLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = SystemLog
        fields = [
            "id",
            "level",
            "action",
            "action_type",
            "message",
            "user",
            "ip_address",
            "user_agent",
            "request_method",
            "request_path",
            "request_data",
            "response_status",
            "execution_time",
            "metadata",
            "stack_trace",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
