"""
Serializer for Organization Members with robust error handling.
"""

from rest_framework import serializers

from apps.organizations.models import OrganizationMembership


class OrganizationMemberSerializer(serializers.ModelSerializer):
    """
    Robust serializer for organization members.
    Uses SerializerMethodField to gracefully handle missing relations.
    """

    user = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    invited_by = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(write_only=True, required=False)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    can_manage_members = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationMembership
        fields = [
            "id",
            "organization",
            "user",
            "user_id",
            "role",
            "role_display",
            "status",
            "permissions",
            "invited_by",
            "invited_at",
            "joined_at",
            "is_active",
            "can_manage_members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "invited_by",
            "invited_at",
            "joined_at",
            "created_at",
            "updated_at",
        ]

    def get_user(self, obj):
        """Get user data with safe fallback."""
        try:
            user = obj.user
            if not user:
                return None

            # Get avatar safely
            avatar_url = None
            try:
                if hasattr(user, "profile") and user.profile and user.profile.avatar:
                    avatar_url = user.profile.avatar.url
            except Exception:
                pass

            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "full_name": user.get_full_name() or user.username,
                "avatar": avatar_url,
            }
        except Exception:
            # Return minimal info if something fails
            return {
                "id": None,
                "username": "Unknown",
                "email": "",
                "full_name": "Unknown User",
                "avatar": None,
            }

    def get_organization(self, obj):
        """Get organization data with safe fallback."""
        try:
            org = obj.organization
            if not org:
                return None

            return {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "organization_type": (
                    org.organization_type if hasattr(org, "organization_type") else None
                ),
            }
        except Exception:
            return None

    def get_invited_by(self, obj):
        """Get inviter data with safe fallback."""
        try:
            if not obj.invited_by:
                return None

            user = obj.invited_by
            return {
                "id": str(user.id),
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
            }
        except Exception:
            return None

    def get_can_manage_members(self, obj):
        """Check if this member can manage other members."""
        try:
            return obj.role in ["owner", "admin", "manager"]
        except Exception:
            return False
