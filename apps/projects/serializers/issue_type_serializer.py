from rest_framework import serializers

from apps.projects.models import IssueType


class IssueTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for IssueType model.
    Used for listing and retrieving issue types available in a project.
    """

    class Meta:
        model = IssueType
        fields = [
            "id",
            "project",
            "name",
            "category",
            "description",
            "icon",
            "color",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class IssueTypeListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing issue types.
    """

    class Meta:
        model = IssueType
        fields = ["id", "name", "category", "icon", "color", "is_default"]
        read_only_fields = fields
