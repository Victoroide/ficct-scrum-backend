from rest_framework import serializers

from apps.integrations.models import GitHubPullRequest
from apps.projects.serializers.issue_serializer import IssueListSerializer


class GitHubPullRequestSerializer(serializers.ModelSerializer):
    is_open = serializers.BooleanField(read_only=True)
    is_merged = serializers.BooleanField(read_only=True)
    status_label = serializers.CharField(read_only=True)

    class Meta:
        model = GitHubPullRequest
        fields = [
            "id",
            "repository",
            "pr_number",
            "title",
            "state",
            "status_label",
            "body",
            "base_branch",
            "head_branch",
            "author",
            "url",
            "additions",
            "deletions",
            "changed_files",
            "commits_count",
            "is_open",
            "is_merged",
            "merged_at",
            "closed_at",
            "created_at",
            "updated_at",
            "synced_at",
        ]
        read_only_fields = [
            "id",
            "pr_number",
            "title",
            "state",
            "body",
            "author",
            "url",
            "additions",
            "deletions",
            "changed_files",
            "commits_count",
            "merged_at",
            "closed_at",
            "created_at",
            "updated_at",
            "synced_at",
        ]


class GitHubPullRequestDetailSerializer(GitHubPullRequestSerializer):
    linked_issues = IssueListSerializer(many=True, read_only=True)

    class Meta(GitHubPullRequestSerializer.Meta):
        fields = GitHubPullRequestSerializer.Meta.fields + ["linked_issues"]


class LinkPullRequestToIssueSerializer(serializers.Serializer):
    issue_id = serializers.UUIDField(required=True)

    def validate_issue_id(self, value):
        from apps.projects.models import Issue

        try:
            Issue.objects.get(id=value)
        except Issue.DoesNotExist:
            raise serializers.ValidationError("Issue not found")
        return value
