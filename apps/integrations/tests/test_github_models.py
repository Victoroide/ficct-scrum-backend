from django.core.exceptions import ValidationError

import pytest

from apps.integrations.models import GitHubCommit, GitHubIntegration, GitHubPullRequest
from apps.integrations.tests.factories import (
    GitHubCommitFactory,
    GitHubIntegrationFactory,
    GitHubPullRequestFactory,
)
from apps.projects.tests.factories import ProjectFactory


@pytest.mark.django_db
class TestGitHubIntegrationModel:
    def test_create_github_integration(self):
        project = ProjectFactory()
        integration = GitHubIntegrationFactory(project=project)

        assert integration.id is not None
        assert integration.project == project
        assert integration.is_active is True
        assert integration.sync_status == "idle"

    def test_repository_full_name_property(self):
        integration = GitHubIntegrationFactory(
            repository_owner="testorg", repository_name="testrepo"
        )
        assert integration.repository_full_name == "testorg/testrepo"

    def test_github_url_property(self):
        integration = GitHubIntegrationFactory(
            repository_owner="testorg", repository_name="testrepo"
        )
        assert integration.github_url == "https://github.com/testorg/testrepo"

    def test_is_connected_property(self):
        integration = GitHubIntegrationFactory()
        assert integration.is_connected is True

        integration.is_active = False
        assert integration.is_connected is False

    def test_set_and_get_access_token(self):
        integration = GitHubIntegrationFactory()
        test_token = "test_github_token_12345"

        integration.set_access_token(test_token)
        integration.save()

        integration.refresh_from_db()
        retrieved_token = integration.get_access_token()

        assert retrieved_token == test_token

    def test_str_representation(self):
        integration = GitHubIntegrationFactory(
            repository_owner="testorg", repository_name="testrepo"
        )
        integration.project.key = "TEST"
        assert "TEST" in str(integration)
        assert "testorg/testrepo" in str(integration)


@pytest.mark.django_db
class TestGitHubCommitModel:
    def test_create_github_commit(self):
        commit = GitHubCommitFactory()

        assert commit.id is not None
        assert commit.sha is not None
        assert commit.repository is not None

    def test_short_sha_property(self):
        commit = GitHubCommitFactory(sha="abc123def456789")
        assert commit.short_sha == "abc123d"
        assert len(commit.short_sha) == 7

    def test_formatted_message_property(self):
        commit = GitHubCommitFactory(message="First line\nSecond line\nThird line")
        assert commit.formatted_message == "First line"

    def test_issue_keys_mentioned_property(self):
        commit = GitHubCommitFactory(message="Fix bug in PROJ-123 and resolve PROJ-456")
        issue_keys = commit.issue_keys_mentioned
        assert "PROJ-123" in issue_keys
        assert "PROJ-456" in issue_keys
        assert len(issue_keys) == 2

    def test_unique_sha_per_repository(self):
        commit1 = GitHubCommitFactory(sha="abc123")

        with pytest.raises(Exception):
            GitHubCommitFactory(repository=commit1.repository, sha="abc123")

    def test_str_representation(self):
        commit = GitHubCommitFactory(sha="abc123def", message="Test commit message")
        assert "abc123d" in str(commit)
        assert "Test commit" in str(commit)


@pytest.mark.django_db
class TestGitHubPullRequestModel:
    def test_create_github_pull_request(self):
        pr = GitHubPullRequestFactory()

        assert pr.id is not None
        assert pr.pr_number is not None
        assert pr.repository is not None

    def test_is_open_property(self):
        pr = GitHubPullRequestFactory(state="open")
        assert pr.is_open is True

        pr.state = "closed"
        assert pr.is_open is False

    def test_is_merged_property(self):
        pr = GitHubPullRequestFactory(state="merged")
        assert pr.is_merged is True

        pr.state = "open"
        assert pr.is_merged is False

    def test_status_label_property(self):
        pr_open = GitHubPullRequestFactory(state="open")
        assert pr_open.status_label == "Open"

        pr_merged = GitHubPullRequestFactory(state="merged")
        assert pr_merged.status_label == "Merged"

        pr_closed = GitHubPullRequestFactory(state="closed")
        assert pr_closed.status_label == "Closed"

    def test_unique_pr_number_per_repository(self):
        pr1 = GitHubPullRequestFactory(pr_number=123)

        with pytest.raises(Exception):
            GitHubPullRequestFactory(repository=pr1.repository, pr_number=123)

    def test_str_representation(self):
        pr = GitHubPullRequestFactory(pr_number=42, title="Feature PR")
        assert "PR #42" in str(pr)
        assert "Feature PR" in str(pr)
