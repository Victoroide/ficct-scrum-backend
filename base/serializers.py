"""
Shared serializers to avoid naming conflicts across apps.
"""
from rest_framework import serializers


class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic user info for nested representation across all apps.
    
    CRITICAL: Must include user_uuid for frontend assignment functionality.
    Frontend expects user_uuid (UUID string) for assignee/reporter fields.
    """

    full_name = serializers.ReadOnlyField()

    class Meta:
        from apps.authentication.models import User

        model = User
        fields = [
            "id",           # Integer ID (for backward compatibility)
            "user_uuid",    # UUID string (REQUIRED for frontend assignments)
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name"
        ]
        read_only_fields = [
            "id",
            "user_uuid",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
        ]


class OrganizationBasicSerializer(serializers.ModelSerializer):
    """Basic organization info for nested representation across all apps."""

    class Meta:
        from apps.organizations.models import Organization

        model = Organization
        fields = ["id", "name", "slug", "organization_type"]
        read_only_fields = ["id", "name", "slug", "organization_type"]


class WorkspaceBasicSerializer(serializers.ModelSerializer):
    """Basic workspace info for nested representation across all apps."""

    class Meta:
        from apps.workspaces.models import Workspace

        model = Workspace
        fields = ["id", "name", "slug", "workspace_type"]
        read_only_fields = ["id", "name", "slug", "workspace_type"]


class ProjectBasicSerializer(serializers.ModelSerializer):
    """Basic project info for nested representation across all apps."""

    class Meta:
        from apps.projects.models import Project

        model = Project
        fields = ["id", "name", "key", "methodology", "status"]
        read_only_fields = ["id", "name", "key", "methodology", "status"]
