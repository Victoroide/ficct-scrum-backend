from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from apps.organizations.models import Organization


class OwnerBasicSerializer(serializers.ModelSerializer):
    """Basic owner info for nested representation."""
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        from apps.authentication.models import User
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.ReadOnlyField()
    workspace_count = serializers.ReadOnlyField()
    logo_url = serializers.SerializerMethodField()
    owner = OwnerBasicSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'slug', 'description', 'logo', 'logo_url', 'website_url',
            'organization_type', 'subscription_plan', 'owner', 'organization_settings',
            'is_active', 'member_count', 'workspace_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']

    @extend_schema_field(OpenApiTypes.STR)
    def get_logo_url(self, obj):
        if obj.logo:
            return obj.logo.url
        return None

    def validate_logo(self, value):
        if value and value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Logo file size cannot exceed 5MB")
        return value
