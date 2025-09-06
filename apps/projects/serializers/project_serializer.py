from rest_framework import serializers
from apps.projects.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    team_member_count = serializers.ReadOnlyField()
    attachments_url = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'workspace', 'name', 'key', 'description', 'methodology',
            'status', 'priority', 'lead', 'start_date', 'end_date',
            'estimated_hours', 'budget', 'attachments', 'attachments_url',
            'project_settings', 'is_active', 'created_by', 'team_member_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_attachments_url(self, obj):
        if obj.attachments:
            return obj.attachments.url
        return None

    def validate_attachments(self, value):
        if value and value.size > 50 * 1024 * 1024:  # 50MB limit
            raise serializers.ValidationError("Attachment file size cannot exceed 50MB")
        return value
