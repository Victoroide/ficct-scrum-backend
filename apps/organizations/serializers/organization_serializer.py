from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.organizations.models import Organization
from base.serializers import UserBasicSerializer


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.ReadOnlyField()
    workspace_count = serializers.ReadOnlyField()
    logo_url = serializers.SerializerMethodField()
    owner = UserBasicSerializer(read_only=True)

    active_projects_count = serializers.IntegerField(read_only=True, required=False)
    team_members_count = serializers.IntegerField(read_only=True, required=False)
    total_workspaces_count = serializers.IntegerField(read_only=True, required=False)

    active_projects_change_pct = serializers.SerializerMethodField()
    team_members_change_pct = serializers.SerializerMethodField()
    total_workspaces_change_pct = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo",
            "logo_url",
            "website_url",
            "organization_type",
            "subscription_plan",
            "owner",
            "organization_settings",
            "is_active",
            "member_count",
            "workspace_count",
            "active_projects_count",
            "active_projects_change_pct",
            "team_members_count",
            "team_members_change_pct",
            "total_workspaces_count",
            "total_workspaces_change_pct",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_logo_url(self, obj):
        if obj.logo:
            return obj.logo.url
        return None

    def validate_logo(self, value):
        if value and value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Logo file size cannot exceed 5MB")
        return value

    def get_active_projects_change_pct(self, obj):
        """Calculate percentage change for active projects."""
        current = getattr(obj, "active_projects_count", None)
        previous = getattr(obj, "prev_active_projects", None)
        return self._calc_pct(current, previous)

    def get_team_members_change_pct(self, obj):
        """Calculate percentage change for team members."""
        current = getattr(obj, "team_members_count", None)
        previous = getattr(obj, "prev_team_members", None)
        return self._calc_pct(current, previous)

    def get_total_workspaces_change_pct(self, obj):
        """Calculate percentage change for workspaces."""
        current = getattr(obj, "total_workspaces_count", None)
        previous = getattr(obj, "prev_workspaces", None)
        return self._calc_pct(current, previous)

    def _calc_pct(self, current, previous):
        """Calculate percentage change between two values."""
        if current is None:
            return None
        if previous and previous > 0:
            return int(((current - previous) / previous) * 100)
        return 100 if current and current > 0 else 0
