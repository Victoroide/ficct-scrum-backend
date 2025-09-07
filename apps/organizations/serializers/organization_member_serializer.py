from rest_framework import serializers
from apps.organizations.models import OrganizationMembership


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested representation."""
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        from apps.authentication.models import User
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name']


class OrganizationBasicSerializer(serializers.ModelSerializer):
    """Basic organization info for nested representation."""
    
    class Meta:
        from apps.organizations.models import Organization
        model = Organization
        fields = ['id', 'name', 'slug', 'organization_type']
        read_only_fields = ['id', 'name', 'slug', 'organization_type']


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    organization = OrganizationBasicSerializer(read_only=True)
    invited_by = UserBasicSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            'id', 'organization', 'user', 'user_id', 'role', 'status', 'permissions',
            'invited_by', 'invited_at', 'joined_at', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'invited_by', 'invited_at', 'joined_at', 'created_at', 'updated_at']
