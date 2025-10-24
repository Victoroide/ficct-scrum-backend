from rest_framework import serializers

from apps.projects.models import WorkflowStatus


class WorkflowStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for WorkflowStatus model.
    
    Returns workflow status details for use in issue status dropdowns and board columns.
    """
    
    class Meta:
        model = WorkflowStatus
        fields = [
            "id",
            "project",
            "name",
            "category",
            "description",
            "color",
            "order",
            "is_initial",
            "is_final",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class WorkflowStatusListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for WorkflowStatus list view.
    
    Returns only essential fields for dropdowns and UI elements.
    """
    
    class Meta:
        model = WorkflowStatus
        fields = [
            "id",
            "name",
            "category",
            "color",
            "order",
            "is_initial",
            "is_final",
        ]
