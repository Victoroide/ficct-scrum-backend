from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.projects.models import Project
from apps.workspaces.models import Workspace
from base.serializers import UserBasicSerializer, WorkspaceBasicSerializer


class ProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for Project model.
    
    Handles workspace assignment using PrimaryKeyRelatedField for automatic
    UUID to instance conversion on both create and update operations.
    """
    team_member_count = serializers.ReadOnlyField()
    attachments_url = serializers.SerializerMethodField()
    attachments = serializers.FileField(required=False, allow_null=True)
    
    # Use PrimaryKeyRelatedField for automatic UUID to instance conversion
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(),
        required=True,
        help_text="UUID of the workspace this project belongs to"
    )
    
    workspace_details = WorkspaceBasicSerializer(source="workspace", read_only=True)
    lead = UserBasicSerializer(read_only=True)
    created_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "workspace",
            "workspace_details",
            "name",
            "key",
            "description",
            "methodology",
            "status",
            "priority",
            "lead",
            "start_date",
            "end_date",
            "estimated_hours",
            "budget",
            "attachments",
            "attachments_url",
            "project_settings",
            "is_active",
            "created_by",
            "team_member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace_details",
            "created_by",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"attachments": {"required": False, "allow_null": True}}

    @extend_schema_field(OpenApiTypes.STR)
    def get_attachments_url(self, obj):
        if obj.attachments:
            return obj.attachments.url
        return None

    def validate_workspace(self, value):
        """
        Validate that the user has access to the workspace.
        
        Args:
            value: Workspace instance (automatically converted from UUID by PrimaryKeyRelatedField)
        
        Returns:
            Validated Workspace instance
        
        Raises:
            ValidationError: If user doesn't have access to workspace
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        # value is already a Workspace instance (converted by PrimaryKeyRelatedField)
        workspace = value
        
        from apps.workspaces.models import WorkspaceMember

        if not WorkspaceMember.objects.filter(
            workspace=workspace, user=request.user, is_active=True
        ).exists():
            raise serializers.ValidationError(
                "You do not have access to this workspace"
            )

        return workspace

    def validate_attachments(self, value):
        """Validate attachment file size."""
        if value and value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("Attachment file size cannot exceed 50MB")
        return value
