from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from apps.projects.models import Project


class WorkspaceBasicSerializer(serializers.ModelSerializer):
    """Basic workspace info for nested representation."""
    
    class Meta:
        from apps.workspaces.models import Workspace
        model = Workspace
        fields = ['id', 'name', 'slug', 'workspace_type']
        read_only_fields = ['id', 'name', 'slug', 'workspace_type']


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested representation."""
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        from apps.authentication.models import User
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']


class ProjectSerializer(serializers.ModelSerializer):
    team_member_count = serializers.ReadOnlyField()
    attachments_url = serializers.SerializerMethodField()
    workspace = WorkspaceBasicSerializer(read_only=True)
    lead = UserBasicSerializer(read_only=True)
    created_by = UserBasicSerializer(read_only=True)

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

    @extend_schema_field(OpenApiTypes.STR)
    def get_attachments_url(self, obj):
        if obj.attachments:
            return obj.attachments.url
        return None

    def validate_attachments(self, value):
        if value and value.size > 50 * 1024 * 1024:  # 50MB limit
            raise serializers.ValidationError("Attachment file size cannot exceed 50MB")
        return value
