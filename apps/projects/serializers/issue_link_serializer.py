from rest_framework import serializers

from apps.projects.models import Issue, IssueLink
from apps.projects.serializers.issue_serializer import IssueListSerializer
from base.serializers import UserBasicSerializer


class IssueLinkSerializer(serializers.ModelSerializer):
    source_issue = IssueListSerializer(read_only=True)
    target_issue = IssueListSerializer(read_only=True)
    source_issue_id = serializers.UUIDField(write_only=True, source="source_issue")
    target_issue_id = serializers.UUIDField(write_only=True, source="target_issue")
    created_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = IssueLink
        fields = [
            "id",
            "source_issue",
            "target_issue",
            "source_issue_id",
            "target_issue_id",
            "link_type",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "source_issue", "target_issue", "created_by", "created_at"]

    def validate_source_issue(self, value):
        try:
            Issue.objects.get(id=value)
        except Issue.DoesNotExist:
            raise serializers.ValidationError("Source issue does not exist")
        return value

    def validate_target_issue(self, value):
        try:
            Issue.objects.get(id=value)
        except Issue.DoesNotExist:
            raise serializers.ValidationError("Target issue does not exist")
        return value

    def validate(self, attrs):
        source_issue_id = attrs.get("source_issue")
        target_issue_id = attrs.get("target_issue")

        if source_issue_id == target_issue_id:
            raise serializers.ValidationError("Cannot link an issue to itself")

        source_issue = Issue.objects.get(id=source_issue_id)
        target_issue = Issue.objects.get(id=target_issue_id)

        if source_issue.project != target_issue.project:
            raise serializers.ValidationError("Both issues must belong to the same project")

        link_type = attrs.get("link_type")
        if IssueLink.objects.filter(
            source_issue=source_issue,
            target_issue=target_issue,
            link_type=link_type
        ).exists():
            raise serializers.ValidationError("This link already exists")

        return attrs

    def create(self, validated_data):
        source_issue_id = validated_data.pop("source_issue")
        target_issue_id = validated_data.pop("target_issue")

        source_issue = Issue.objects.get(id=source_issue_id)
        target_issue = Issue.objects.get(id=target_issue_id)

        validated_data["source_issue"] = source_issue
        validated_data["target_issue"] = target_issue
        validated_data["created_by"] = self.context["request"].user

        link = super().create(validated_data)

        reciprocal_link_type = IssueLink.get_reciprocal_link_type(validated_data["link_type"])

        if not IssueLink.objects.filter(
            source_issue=target_issue,
            target_issue=source_issue,
            link_type=reciprocal_link_type
        ).exists():
            IssueLink.objects.create(
                source_issue=target_issue,
                target_issue=source_issue,
                link_type=reciprocal_link_type,
                created_by=self.context["request"].user
            )

        return link
