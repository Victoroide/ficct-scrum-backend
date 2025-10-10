from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.integrations.models import GitHubIntegration
from apps.integrations.services.github_service import GitHubService


class GitHubIntegrationSerializer(serializers.ModelSerializer):
    access_token = serializers.CharField(write_only=True, required=True)
    repository_full_name = serializers.CharField(read_only=True)
    github_url = serializers.CharField(read_only=True)
    is_connected = serializers.BooleanField(read_only=True)

    class Meta:
        model = GitHubIntegration
        fields = [
            "id",
            "project",
            "repository_url",
            "repository_owner",
            "repository_name",
            "repository_full_name",
            "github_url",
            "access_token",
            "is_active",
            "last_sync_at",
            "sync_status",
            "auto_link_commits",
            "smart_commits_enabled",
            "sync_pull_requests",
            "connected_at",
            "updated_at",
            "is_connected",
        ]
        read_only_fields = [
            "id",
            "repository_owner",
            "repository_name",
            "last_sync_at",
            "sync_status",
            "connected_at",
            "updated_at",
        ]

    def validate_repository_url(self, value):
        if not value.startswith("https://github.com/"):
            raise serializers.ValidationError(
                "Repository URL must be a valid GitHub repository URL"
            )
        return value

    def create(self, validated_data):
        access_token = validated_data.pop("access_token")
        project = validated_data.get("project")
        repository_url = validated_data.get("repository_url")

        service = GitHubService()
        try:
            integration = service.connect_repository(
                project, repository_url, access_token
            )
            return integration
        except ValueError as e:
            raise serializers.ValidationError({"access_token": str(e)})


class GitHubIntegrationDetailSerializer(GitHubIntegrationSerializer):
    commits_count = serializers.SerializerMethodField()
    pull_requests_count = serializers.SerializerMethodField()

    class Meta(GitHubIntegrationSerializer.Meta):
        fields = GitHubIntegrationSerializer.Meta.fields + [
            "commits_count",
            "pull_requests_count",
        ]

    @extend_schema_field(serializers.IntegerField)
    def get_commits_count(self, obj) -> int:
        return obj.commits.count()

    @extend_schema_field(serializers.IntegerField)
    def get_pull_requests_count(self, obj) -> int:
        return obj.pull_requests.count()
