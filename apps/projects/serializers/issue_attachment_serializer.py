from rest_framework import serializers

from apps.projects.models import IssueAttachment
from base.serializers import UserBasicSerializer


class IssueAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserBasicSerializer(read_only=True)
    file_url = serializers.ReadOnlyField()
    file_size_mb = serializers.ReadOnlyField()

    class Meta:
        model = IssueAttachment
        fields = [
            "id",
            "file",
            "filename",
            "file_size",
            "file_size_mb",
            "content_type",
            "file_url",
            "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = [
            "id",
            "filename",
            "file_size",
            "file_size_mb",
            "content_type",
            "file_url",
            "uploaded_by",
            "uploaded_at",
        ]

    def validate_file(self, value):
        max_size = 50 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                "File size cannot exceed 50MB"
            )
        return value

    def create(self, validated_data):
        file = validated_data["file"]
        validated_data["filename"] = file.name
        validated_data["file_size"] = file.size
        validated_data["content_type"] = file.content_type
        validated_data["uploaded_by"] = self.context["request"].user
        return super().create(validated_data)
