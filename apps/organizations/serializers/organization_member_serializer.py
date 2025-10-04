from rest_framework import serializers

from apps.organizations.models import OrganizationMembership
from base.serializers import OrganizationBasicSerializer, UserBasicSerializer


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    organization = OrganizationBasicSerializer(read_only=True)
    invited_by = UserBasicSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            "id",
            "organization",
            "user",
            "user_id",
            "role",
            "status",
            "permissions",
            "invited_by",
            "invited_at",
            "joined_at",
            "is_active",
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
