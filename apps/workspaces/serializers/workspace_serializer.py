from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.organizations.models import Organization
from apps.workspaces.models import Workspace
from base.serializers import OrganizationBasicSerializer, UserBasicSerializer


class WorkspaceSerializer(serializers.ModelSerializer):
    member_count = serializers.ReadOnlyField()
    project_count = serializers.ReadOnlyField()
    cover_image_url = serializers.SerializerMethodField()
    organization = serializers.UUIDField(write_only=True, required=True)
    organization_details = OrganizationBasicSerializer(
        source="organization", read_only=True
    )
    created_by = UserBasicSerializer(read_only=True)

    active_projects_count = serializers.IntegerField(read_only=True, required=False)
    team_members_count = serializers.IntegerField(read_only=True, required=False)

    active_projects_change_pct = serializers.SerializerMethodField()
    team_members_change_pct = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id",
            "organization",
            "organization_details",
            "name",
            "slug",
            "description",
            "workspace_type",
            "visibility",
            "cover_image",
            "cover_image_url",
            "workspace_settings",
            "is_active",
            "created_by",
            "member_count",
            "project_count",
            "active_projects_count",
            "active_projects_change_pct",
            "team_members_count",
            "team_members_change_pct",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization_details",
            "created_by",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_cover_image_url(self, obj):
        if obj.cover_image:
            return obj.cover_image.url
        return None

    def validate_organization(self, value):
        """Validate that organization exists and user has access."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        try:
            organization = Organization.objects.get(id=value)
        except Organization.DoesNotExist:
            raise serializers.ValidationError("Organization does not exist")

        # Check if user is a member of the organization
        from apps.organizations.models import OrganizationMembership

        if not OrganizationMembership.objects.filter(
            organization=organization, user=request.user, is_active=True
        ).exists():
            raise serializers.ValidationError(
                "You do not have access to this organization"
            )

        return value

    def validate_slug(self, value):
        """Validate slug is unique within organization."""
        organization_id = self.initial_data.get("organization")
        if organization_id:
            queryset = Workspace.objects.filter(
                organization_id=organization_id, slug=value
            )
            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)
            if queryset.exists():
                raise serializers.ValidationError(
                    "Workspace with this slug already exists in this organization"
                )
        return value

    def validate_cover_image(self, value):
        if value and value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Cover image file size cannot exceed 5MB")
        return value

    def create(self, validated_data):
        """Handle organization assignment during creation."""
        organization_id = validated_data.pop("organization")
        organization = Organization.objects.get(id=organization_id)
        validated_data["organization"] = organization

        workspace = super().create(validated_data)

        # Create workspace membership for creator
        from apps.workspaces.models import WorkspaceMember

        WorkspaceMember.objects.create(
            workspace=workspace,
            user=validated_data["created_by"],
            role="admin",
            is_active=True,
        )

        return workspace

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

    def _calc_pct(self, current, previous):
        """Calculate percentage change between two values."""
        if current is None:
            return None
        if previous and previous > 0:
            return int(((current - previous) / previous) * 100)
        return 100 if current and current > 0 else 0
