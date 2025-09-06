from rest_framework import serializers
from apps.organizations.models import OrganizationMembership
from apps.authentication.serializers import UserSerializer


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            'id', 'organization', 'user', 'user_id', 'role', 'status', 'permissions',
            'invited_by', 'invited_at', 'joined_at', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'invited_by', 'invited_at', 'joined_at', 'created_at', 'updated_at']
