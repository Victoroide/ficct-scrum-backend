from rest_framework import serializers

from apps.reporting.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    formatted_action = serializers.CharField(read_only=True)
    time_ago = serializers.CharField(read_only=True)
    action_display = serializers.CharField(
        source="get_action_type_display", read_only=True
    )

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "action_type",
            "action_display",
            "object_repr",
            "changes",
            "formatted_action",
            "time_ago",
            "created_at",
        ]
        read_only_fields = fields
