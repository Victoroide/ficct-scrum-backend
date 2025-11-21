from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.projects.models import Project, ProjectTeamMember
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

    team_members_count = serializers.IntegerField(read_only=True, required=False)
    active_issues_count = serializers.IntegerField(read_only=True, required=False)

    team_members_change_pct = serializers.SerializerMethodField()
    active_issues_change_pct = serializers.SerializerMethodField()

    # Use PrimaryKeyRelatedField for automatic UUID to instance conversion
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(),
        required=True,
        help_text="UUID of the workspace this project belongs to",
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
            "team_members_count",
            "team_members_change_pct",
            "active_issues_count",
            "active_issues_change_pct",
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
            value: Workspace instance (automatically converted from UUID by PrimaryKeyRelatedField)  # noqa: E501

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

    def get_team_members_change_pct(self, obj):
        """Calculate percentage change for team members."""
        current = getattr(obj, "team_members_count", None)
        previous = getattr(obj, "prev_team_members", None)
        return self._calc_pct(current, previous)

    def get_active_issues_change_pct(self, obj):
        """Calculate percentage change for active issues."""
        current = getattr(obj, "active_issues_count", None)
        previous = getattr(obj, "prev_issues", None)
        return self._calc_pct(current, previous)

    def _calc_pct(self, current, previous):
        """Calculate percentage change between two values."""
        if current is None:
            return None
        if previous and previous > 0:
            return int(((current - previous) / previous) * 100)
        return 100 if current and current > 0 else 0


class ProjectTeamMemberSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for ProjectTeamMember model.

    Note: Does NOT include full project data to avoid N+1 queries.
    Client already knows project ID from URL path.
    """

    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = ProjectTeamMember
        fields = [
            "id",
            "user",
            "role",
            "permissions",
            "hourly_rate",
            "is_active",
            "joined_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "joined_at", "updated_at"]


class AddTeamMemberSerializer(serializers.Serializer):
    """Serializer for adding team members to a project."""

    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(
        choices=ProjectTeamMember.ROLE_CHOICES, default="developer"
    )
    hourly_rate = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )

    def validate_user_id(self, value):
        """Validate that user exists and is active."""
        from apps.authentication.models import User

        try:
            _user = User.objects.get(id=value, is_active=True)  # noqa: F841
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found or inactive")
        return value

    @transaction.atomic
    def save(self):
        """
        Create or reactivate project team member.

        Validates that the user is a workspace member before adding to project.
        """
        project = self.context.get("project")
        user_id = self.validated_data["user_id"]
        role = self.validated_data["role"]
        hourly_rate = self.validated_data.get("hourly_rate")

        from apps.authentication.models import User
        from apps.workspaces.models import WorkspaceMember

        user = User.objects.get(id=user_id)

        # Validate that user is a workspace member
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=user, is_active=True
        ).exists()

        if not is_workspace_member:
            raise serializers.ValidationError(
                "User must be a workspace member before being added to a project"
            )

        # Check if user is already a team member
        existing_member = ProjectTeamMember.objects.filter(
            project=project, user=user
        ).first()

        if existing_member:
            if existing_member.is_active:
                raise serializers.ValidationError("User is already a team member")
            else:
                # Reactivate existing membership
                existing_member.is_active = True
                existing_member.role = role
                if hourly_rate is not None:
                    existing_member.hourly_rate = hourly_rate
                existing_member.save()
                return existing_member

        # Create new team membership
        return ProjectTeamMember.objects.create(
            project=project, user=user, role=role, hourly_rate=hourly_rate
        )
