from rest_framework import serializers

from apps.reporting.models import ActivityLog
from base.serializers import (
    OrganizationBasicSerializer,
    ProjectBasicSerializer,
    UserBasicSerializer,
    WorkspaceBasicSerializer,
)


class ActivityLogSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for Activity Logs with full context.
    
    Includes user information, scope (organization/workspace/project),
    action details, object information, and time formatting.
    Similar to Jira's Activity Stream item structure.
    """
    # User information
    user_detail = UserBasicSerializer(source="user", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    
    # Scope information (hierarchy)
    project_detail = ProjectBasicSerializer(source="project", read_only=True)
    workspace_detail = WorkspaceBasicSerializer(source="workspace", read_only=True)
    organization_detail = OrganizationBasicSerializer(source="organization", read_only=True)
    
    # Action information
    action_display = serializers.CharField(
        source="get_action_type_display", read_only=True
    )
    formatted_action = serializers.CharField(read_only=True)
    
    # Object information
    object_type = serializers.SerializerMethodField()
    object_url = serializers.SerializerMethodField()
    
    # Time information
    time_ago = serializers.CharField(read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            # IDs
            "id",
            "user",
            "project",
            "workspace",
            "organization",
            
            # User details
            "user_detail",
            "user_email",
            "user_name",
            
            # Scope details
            "project_detail",
            "workspace_detail",
            "organization_detail",
            
            # Action details
            "action_type",
            "action_display",
            "formatted_action",
            
            # Object details
            "object_repr",
            "object_type",
            "object_url",
            "object_id",
            "changes",
            
            # Meta
            "ip_address",
            "time_ago",
            "created_at",
        ]
        read_only_fields = fields
    
    def get_object_type(self, obj):
        """
        Get human-readable object type from ContentType.
        
        Returns:
            str: Model name (e.g., 'issue', 'sprint', 'board')
        """
        if obj.content_type:
            return obj.content_type.model
        return None
    
    def get_object_url(self, obj):
        """
        Generate frontend URL for the object based on type.
        
        Returns:
            str: Relative URL path to view the object in frontend
        """
        if not obj.content_type or not obj.object_id:
            return None
        
        model = obj.content_type.model
        object_id = obj.object_id
        
        # Generate URLs based on object type
        url_patterns = {
            'issue': f'/projects/{obj.project.key if obj.project else "unknown"}/issues/{object_id}',
            'sprint': f'/projects/{obj.project.key if obj.project else "unknown"}/sprints/{object_id}',
            'board': f'/projects/{obj.project.key if obj.project else "unknown"}/boards/{object_id}',
            'project': f'/projects/{object_id}',
            'workspace': f'/workspaces/{object_id}',
            'organization': f'/organizations/{object_id}',
        }
        
        return url_patterns.get(model)
