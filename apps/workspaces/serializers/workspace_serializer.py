from rest_framework import serializers
from apps.workspaces.models import Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    member_count = serializers.ReadOnlyField()
    project_count = serializers.ReadOnlyField()
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            'id', 'organization', 'name', 'slug', 'description', 'workspace_type',
            'visibility', 'cover_image', 'cover_image_url', 'workspace_settings',
            'is_active', 'created_by', 'member_count', 'project_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_cover_image_url(self, obj):
        if obj.cover_image:
            return obj.cover_image.url
        return None

    def validate_cover_image(self, value):
        if value and value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Cover image file size cannot exceed 5MB")
        return value
