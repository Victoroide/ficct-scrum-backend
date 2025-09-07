from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

from apps.authentication.models import UserProfile


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested representation."""
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        from apps.authentication.models import User
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer aligned with UserProfile model definition."""

    avatar_url = serializers.SerializerMethodField()
    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'avatar', 'avatar_url', 'bio', 'phone_number', 'timezone',
            'language', 'github_username', 'linkedin_url', 'website_url',
            'notification_preferences', 'is_online', 'last_activity',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'avatar_url', 'is_online', 'last_activity',
            'created_at', 'updated_at'
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_avatar_url(self, obj):
        return obj.avatar.url if getattr(obj, 'avatar', None) else None
