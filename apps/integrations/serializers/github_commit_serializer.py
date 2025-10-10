from rest_framework import serializers

from apps.integrations.models import GitHubCommit
from apps.projects.serializers.issue_serializer import IssueListSerializer


class GitHubCommitSerializer(serializers.ModelSerializer):
    short_sha = serializers.CharField(read_only=True)
    formatted_message = serializers.CharField(read_only=True)
    issue_keys_mentioned = serializers.ListField(read_only=True)

    class Meta:
        model = GitHubCommit
        fields = [
            "id",
            "repository",
            "sha",
            "short_sha",
            "message",
            "formatted_message",
            "author_name",
            "author_email",
            "commit_date",
            "branch",
            "url",
            "issue_keys_mentioned",
            "synced_at",
        ]
        read_only_fields = [
            "id",
            "sha",
            "message",
            "author_name",
            "author_email",
            "commit_date",
            "url",
            "synced_at",
        ]


class GitHubCommitDetailSerializer(GitHubCommitSerializer):
    linked_issues = IssueListSerializer(many=True, read_only=True)

    class Meta(GitHubCommitSerializer.Meta):
        fields = GitHubCommitSerializer.Meta.fields + ["linked_issues"]


class LinkCommitToIssueSerializer(serializers.Serializer):
    issue_id = serializers.UUIDField(required=True)

    def validate_issue_id(self, value):
        from apps.projects.models import Issue

        try:
            Issue.objects.get(id=value)
        except Issue.DoesNotExist:
            raise serializers.ValidationError("Issue not found")
        return value
