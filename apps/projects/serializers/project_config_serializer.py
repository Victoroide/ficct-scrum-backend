from rest_framework import serializers

from apps.projects.models import ProjectConfiguration
from base.serializers import ProjectBasicSerializer


class ProjectConfigSerializer(serializers.ModelSerializer):
    project = ProjectBasicSerializer(read_only=True)

    class Meta:
        model = ProjectConfiguration
        fields = [
            "project",
            "sprint_duration",
            "auto_close_sprints",
            "estimation_type",
            "story_point_scale",
            "enable_time_tracking",
            "require_time_logging",
            "enable_sub_tasks",
            "email_notifications",
            "slack_notifications",
            "slack_webhook_url",
            "restrict_issue_visibility",
            "require_approval_for_changes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["project", "created_at", "updated_at"]
