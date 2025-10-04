from rest_framework import serializers

from apps.projects.models import IssueComment
from base.serializers import UserBasicSerializer


class IssueCommentSerializer(serializers.ModelSerializer):
    author = UserBasicSerializer(read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = IssueComment
        fields = [
            "id",
            "content",
            "author",
            "is_edited",
            "edited_at",
            "can_edit",
            "can_delete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author",
            "is_edited",
            "edited_at",
            "can_edit",
            "can_delete",
            "created_at",
            "updated_at",
        ]

    def get_can_edit(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.can_edit(request.user)
        return False

    def get_can_delete(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.can_delete(request.user)
        return False

    def update(self, instance, validated_data):
        from datetime import datetime

        instance.content = validated_data.get("content", instance.content)
        instance.is_edited = True
        instance.edited_at = datetime.now()
        instance.save()
        return instance
