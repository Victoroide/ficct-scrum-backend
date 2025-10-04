from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.authentication.models import UserProfile
from base.serializers import UserBasicSerializer


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer aligned with UserProfile model definition."""

    avatar_url = serializers.SerializerMethodField()
    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "user",
            "avatar",
            "avatar_url",
            "bio",
            "phone_number",
            "timezone",
            "language",
            "github_username",
            "linkedin_url",
            "website_url",
            "notification_preferences",
            "is_online",
            "last_activity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "user",
            "avatar_url",
            "is_online",
            "last_activity",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_avatar_url(self, obj):
        return obj.avatar.url if getattr(obj, "avatar", None) else None
