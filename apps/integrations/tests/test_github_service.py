"""
Comprehensive tests for GitHubService.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.utils import timezone

from apps.integrations.models import GitHubCommit, GitHubIntegration
from apps.integrations.services.github_service import GitHubService
from apps.integrations.tests.factories import GitHubIntegrationFactory
from apps.projects.models import Issue
from apps.projects.tests.factories import IssueFactory, ProjectFactory


@pytest.mark.django_db
class TestGitHubService:
    """Test GitHub service methods."""

    def setup_method(self):
        """Set up test dependencies."""
        self.service = GitHubService()
        self.project = ProjectFactory()

    def test_connect_repository_valid_url(self):
        """Test connecting to a valid GitHub repository."""
        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_repo = Mock()
            mock_repo.full_name = "owner/repo"
            mock_repo.html_url = "https://github.com/owner/repo"
            mock_repo.default_branch = "main"
            mock_github.return_value.get_repo.return_value = mock_repo

            integration = self.service.connect_repository(
                project=self.project,
                repository_url="https://github.com/owner/repo",
                access_token="test_token",
            )

            assert integration.repository_name == "owner/repo"
            assert integration.is_active is True
            assert integration.repository_url == "https://github.com/owner/repo"

    def test_connect_repository_invalid_url(self):
        """Test connecting with invalid repository URL."""
        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_github.return_value.get_repo.side_effect = Exception("Repo not found")

            integration = self.service.connect_repository(
                project=self.project,
                repository_url="https://github.com/invalid/repo",
                access_token="test_token",
            )

            assert integration is None

    def test_verify_access_valid_token(self):
        """Test verifying valid access token."""
        integration = GitHubIntegrationFactory(project=self.project)
        integration.set_access_token("valid_token")
        integration.save()

        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_user = Mock()
            mock_user.login = "testuser"
            mock_github.return_value.get_user.return_value = mock_user

            result = self.service.verify_access(integration)
            assert result is True

    def test_verify_access_invalid_token(self):
        """Test verifying invalid access token."""
        integration = GitHubIntegrationFactory(project=self.project)
        integration.set_access_token("invalid_token")
        integration.save()

        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_github.return_value.get_user.side_effect = Exception("Bad credentials")

            result = self.service.verify_access(integration)
            assert result is False

    def test_sync_commits_success(self):
        """Test syncing commits from GitHub."""
        integration = GitHubIntegrationFactory(
            project=self.project, repository_name="owner/repo"
        )
        integration.set_access_token("valid_token")
        integration.save()

        with patch("apps.integrations.services.github_service.Github") as mock_github:
            # Mock commit data
            mock_commit = Mock()
            mock_commit.sha = "abc123"
            mock_commit.commit.message = "Test commit message"
            mock_commit.commit.author.name = "Test Author"
            mock_commit.commit.author.email = "test@example.com"
            mock_commit.commit.author.date = datetime(2025, 10, 10, 10, 0, 0)
            mock_commit.html_url = "https://github.com/owner/repo/commit/abc123"

            mock_repo = Mock()
            mock_repo.get_commits.return_value = [mock_commit]
            mock_github.return_value.get_repo.return_value = mock_repo

            count = self.service.sync_commits(integration)

            assert count == 1
            assert GitHubCommit.objects.count() == 1
            commit = GitHubCommit.objects.first()
            assert commit.sha == "abc123"
            assert commit.message == "Test commit message"

    def test_sync_commits_no_new_commits(self):
        """Test syncing when no new commits exist."""
        integration = GitHubIntegrationFactory(project=self.project)
        integration.set_access_token("valid_token")
        integration.save()

        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_repo = Mock()
            mock_repo.get_commits.return_value = []
            mock_github.return_value.get_repo.return_value = mock_repo

            count = self.service.sync_commits(integration)
            assert count == 0

    def test_parse_commit_message_with_issue_key(self):
        """Test parsing commit message with issue key."""
        message = "fixes PROJ-123: Fix authentication bug"
        issue_keys = self.service.parse_commit_message(message)

        assert "PROJ-123" in issue_keys

    def test_parse_commit_message_multiple_keys(self):
        """Test parsing commit message with multiple issue keys."""
        message = "Implemented PROJ-45 and PROJ-46, closes PROJ-47"
        issue_keys = self.service.parse_commit_message(message)

        assert len(issue_keys) == 3
        assert "PROJ-45" in issue_keys
        assert "PROJ-46" in issue_keys
        assert "PROJ-47" in issue_keys

    def test_parse_commit_message_no_keys(self):
        """Test parsing commit message without issue keys."""
        message = "Regular commit without issue reference"
        issue_keys = self.service.parse_commit_message(message)

        assert len(issue_keys) == 0

    def test_process_smart_commit_fixes_keyword(self):
        """Test smart commit with 'fixes' keyword."""
        issue = IssueFactory(project=self.project, key_prefix="PROJ", key_number=123)

        # Create a done status
        done_status = issue.project.statuses.filter(category="done").first()
        if not done_status:
            from apps.projects.tests.factories import WorkflowStatusFactory

            done_status = WorkflowStatusFactory(
                project=issue.project, name="Done", category="done"
            )

        message = "fixes PROJ-123: Fixed the bug"

        result = self.service.process_smart_commit(issue, message)

        assert result is True
        issue.refresh_from_db()
        assert issue.status.category == "done"
        assert issue.resolved_at is not None

    def test_process_smart_commit_closes_keyword(self):
        """Test smart commit with 'closes' keyword."""
        issue = IssueFactory(project=self.project, key_prefix="PROJ", key_number=456)

        done_status = issue.project.statuses.filter(category="done").first()
        if not done_status:
            from apps.projects.tests.factories import WorkflowStatusFactory

            done_status = WorkflowStatusFactory(
                project=issue.project, name="Done", category="done"
            )

        message = "closes PROJ-456: Implemented feature"

        result = self.service.process_smart_commit(issue, message)

        assert result is True
        issue.refresh_from_db()
        assert issue.status.category == "done"

    def test_process_smart_commit_no_keyword(self):
        """Test smart commit without action keyword."""
        issue = IssueFactory(project=self.project, key_prefix="PROJ", key_number=789)
        original_status = issue.status

        message = "PROJ-789: Work in progress"

        result = self.service.process_smart_commit(issue, message)

        assert result is False
        issue.refresh_from_db()
        assert issue.status == original_status

    def test_link_commit_to_issues(self):
        """Test linking commit to issues."""
        integration = GitHubIntegrationFactory(project=self.project)
        issue1 = IssueFactory(project=self.project, key_prefix="PROJ", key_number=100)
        issue2 = IssueFactory(project=self.project, key_prefix="PROJ", key_number=101)

        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_commit = Mock()
            mock_commit.sha = "xyz789"
            mock_commit.commit.message = "Implemented PROJ-100 and PROJ-101"
            mock_commit.commit.author.name = "Dev"
            mock_commit.commit.author.email = "dev@example.com"
            mock_commit.commit.author.date = datetime(2025, 10, 10, 10, 0, 0)
            mock_commit.html_url = "https://github.com/owner/repo/commit/xyz789"

            mock_repo = Mock()
            mock_repo.get_commits.return_value = [mock_commit]
            mock_github.return_value.get_repo.return_value = mock_repo

            integration.set_access_token("token")
            integration.save()

            self.service.sync_commits(integration)

        commit = GitHubCommit.objects.get(sha="xyz789")
        assert commit.linked_issues.count() == 2
        assert issue1 in commit.linked_issues.all()
        assert issue2 in commit.linked_issues.all()

    def test_calculate_code_metrics(self):
        """Test calculating code metrics."""
        integration = GitHubIntegrationFactory(project=self.project)
        integration.set_access_token("valid_token")
        integration.save()

        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_repo = Mock()
            mock_repo.get_commits.return_value = [Mock(), Mock(), Mock()]
            mock_repo.get_pulls.return_value = [Mock(), Mock()]
            mock_repo.get_contributors.return_value = [Mock(), Mock(), Mock(), Mock()]
            mock_github.return_value.get_repo.return_value = mock_repo

            metrics = self.service.calculate_code_metrics(integration)

            assert metrics["total_commits"] == 3
            assert metrics["total_pull_requests"] == 2
            assert metrics["total_contributors"] == 4

    def test_sync_pull_requests_success(self):
        """Test syncing pull requests from GitHub."""
        integration = GitHubIntegrationFactory(project=self.project)
        integration.set_access_token("valid_token")
        integration.save()

        with patch("apps.integrations.services.github_service.Github") as mock_github:
            mock_pr = Mock()
            mock_pr.number = 42
            mock_pr.title = "Test PR"
            mock_pr.body = "Test description"
            mock_pr.state = "open"
            mock_pr.html_url = "https://github.com/owner/repo/pull/42"
            mock_pr.user.login = "testuser"
            mock_pr.created_at = datetime(2025, 10, 1, 10, 0, 0)
            mock_pr.updated_at = datetime(2025, 10, 10, 10, 0, 0)
            mock_pr.merged_at = None
            mock_pr.closed_at = None

            mock_repo = Mock()
            mock_repo.get_pulls.return_value = [mock_pr]
            mock_github.return_value.get_repo.return_value = mock_repo

            count = self.service.sync_pull_requests(integration)

            assert count == 1
            from apps.integrations.models import GitHubPullRequest

            assert GitHubPullRequest.objects.count() == 1
            pr = GitHubPullRequest.objects.first()
            assert pr.number == 42
            assert pr.title == "Test PR"
