from rest_framework import serializers

from apps.authentication.serializers import UserSerializer
from apps.logging.models import ErrorLog


class ErrorLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)

    class Meta:
        model = ErrorLog
        fields = [
            "id",
            "error_type",
            "error_message",
            "stack_trace",
            "severity",
            "status",
            "user",
            "ip_address",
            "request_data",
            "environment_info",
            "occurrence_count",
            "first_occurrence",
            "last_occurrence",
            "resolved_by",
            "resolved_at",
            "resolution_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "ip_address",
            "request_data",
            "environment_info",
            "occurrence_count",
            "first_occurrence",
            "last_occurrence",
            "created_at",
            "updated_at",
        ]
