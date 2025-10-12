from rest_framework import serializers

from apps.projects.models import ProjectConfiguration
from base.serializers import ProjectBasicSerializer


class ProjectConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for ProjectConfiguration model.
    
    Handles both creation (accepts project UUID) and retrieval (returns nested project details).
    The slack_webhook_url field is completely optional.
    """
    
    # For writing: accept UUID
    project = serializers.PrimaryKeyRelatedField(
        queryset=ProjectConfiguration.objects.none(),
        required=True,
        help_text="UUID of the project to configure"
    )
    
    # For Slack integration: make webhook URL completely optional
    slack_webhook_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Slack webhook URL for notifications (optional)"
    )

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
        read_only_fields = ["created_at", "updated_at"]
    
    def __init__(self, *args, **kwargs):
        """Initialize the serializer with proper project queryset."""
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from apps.projects.models import Project
        self.fields['project'].queryset = Project.objects.all()
    
    def validate(self, attrs):
        """
        Validate that a configuration doesn't already exist for the project.
        
        This prevents UniqueViolation errors and provides clear error messages.
        """
        project = attrs.get('project')
        
        # Only check for duplicates on creation (not on update)
        if self.instance is None and project:
            if ProjectConfiguration.objects.filter(project=project).exists():
                raise serializers.ValidationError({
                    'project': 'A configuration already exists for this project.'
                })
        
        return attrs
    
    def to_representation(self, instance):
        """
        Override to return nested ProjectBasicSerializer for reading.
        
        This allows us to accept UUID on write but return full project details on read.
        """
        representation = super().to_representation(instance)
        representation['project'] = ProjectBasicSerializer(instance.project).data
        return representation
