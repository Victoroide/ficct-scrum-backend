from rest_framework import serializers

from apps.authentication.models import User
from apps.authentication.serializers import UserSerializer
from apps.workspaces.models import Workspace, WorkspaceMember


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = WorkspaceMember
        fields = [
            "id",
            "workspace",
            "user",
            "user_id",
            "role",
            "permissions",
            "is_active",
            "joined_at",
            "updated_at",
        ]
        read_only_fields = ["id", "joined_at", "updated_at"]

    def validate(self, attrs):
        """Validate that user belongs to the workspace's parent organization."""
        user_id = attrs.get("user_id")
        workspace = attrs.get("workspace")

        if user_id and workspace:
            # Get the user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({"user_id": "User does not exist"})

            # Check if user is a member of the parent organization
            from apps.organizations.models import OrganizationMembership

            is_org_member = OrganizationMembership.objects.filter(
                organization=workspace.organization, user=user, is_active=True
            ).exists()

            if not is_org_member:
                raise serializers.ValidationError(
                    "User must be a member of the parent organization "
                    f"({workspace.organization.name}) before being added "
                    "to this workspace."
                )

            attrs["user"] = user

        return attrs

    def create(self, validated_data):
        """Create workspace member with validated user."""
        user_id = validated_data.pop("user_id", None)
        if "user" not in validated_data and user_id:
            validated_data["user"] = User.objects.get(id=user_id)

        return super().create(validated_data)
