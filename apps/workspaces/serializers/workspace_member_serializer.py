from rest_framework import serializers
from apps.workspaces.models import WorkspaceMember
from apps.authentication.serializers import UserSerializer


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = WorkspaceMember
        fields = [
            'id', 'workspace', 'user', 'user_id', 'role', 'permissions',
            'is_active', 'joined_at', 'updated_at'
        ]
        read_only_fields = ['id', 'joined_at', 'updated_at']
