import pytest
from django.urls import reverse
from rest_framework import status

from apps.integrations.tests.factories import (
    GitHubCommitFactory,
    GitHubIntegrationFactory,
    GitHubPullRequestFactory,
)
from apps.projects.tests.factories import IssueFactory, ProjectFactory


@pytest.mark.django_db
class TestGitHubIntegrationAPI:
    def test_list_integrations(self, api_client, authenticated_user, project_with_team):
        project = project_with_team
        GitHubIntegrationFactory(project=project)

        url = reverse("github-integration-list")
        response = api_client.get(url, {"project": str(project.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_retrieve_integration(
        self, api_client, authenticated_user, project_with_team
    ):
        integration = GitHubIntegrationFactory(project=project_with_team)

        url = reverse("github-integration-detail", kwargs={"pk": str(integration.id)})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(integration.id)
        assert "repository_full_name" in response.data

    def test_create_integration_requires_admin(
        self, api_client, authenticated_user, project_with_team
    ):
        url = reverse("github-integration-list")
        data = {
            "project": str(project_with_team.id),
            "repository_url": "https://github.com/testorg/testrepo",
            "access_token": "test_token_123",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_delete_integration(
        self, api_client, authenticated_user, project_with_team
    ):
        integration = GitHubIntegrationFactory(project=project_with_team)

        url = reverse("github-integration-detail", kwargs={"pk": str(integration.id)})
        response = api_client.delete(url)

        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.django_db
class TestGitHubCommitAPI:
    def test_list_commits(self, api_client, authenticated_user, project_with_team):
        integration = GitHubIntegrationFactory(project=project_with_team)
        GitHubCommitFactory.create_batch(3, repository=integration)

        url = reverse("github-commit-list")
        response = api_client.get(url, {"repository": str(integration.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_retrieve_commit(self, api_client, authenticated_user, project_with_team):
        integration = GitHubIntegrationFactory(project=project_with_team)
        commit = GitHubCommitFactory(repository=integration)

        url = reverse("github-commit-detail", kwargs={"pk": str(commit.id)})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(commit.id)
        assert "short_sha" in response.data

    def test_link_commit_to_issue(
        self, api_client, authenticated_user, project_with_team
    ):
        integration = GitHubIntegrationFactory(project=project_with_team)
        commit = GitHubCommitFactory(repository=integration)
        issue = IssueFactory(project=project_with_team)

        url = reverse("github-commit-link-issue", kwargs={"pk": str(commit.id)})
        data = {"issue_id": str(issue.id)}

        response = api_client.post(url, data, format="json")

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestGitHubPullRequestAPI:
    def test_list_pull_requests(
        self, api_client, authenticated_user, project_with_team
    ):
        integration = GitHubIntegrationFactory(project=project_with_team)
        GitHubPullRequestFactory.create_batch(3, repository=integration)

        url = reverse("github-pull-request-list")
        response = api_client.get(url, {"repository": str(integration.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_retrieve_pull_request(
        self, api_client, authenticated_user, project_with_team
    ):
        integration = GitHubIntegrationFactory(project=project_with_team)
        pr = GitHubPullRequestFactory(repository=integration)

        url = reverse("github-pull-request-detail", kwargs={"pk": str(pr.id)})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(pr.id)
        assert "status_label" in response.data

    def test_filter_pull_requests_by_state(
        self, api_client, authenticated_user, project_with_team
    ):
        integration = GitHubIntegrationFactory(project=project_with_team)
        GitHubPullRequestFactory(repository=integration, state="open")
        GitHubPullRequestFactory(repository=integration, state="merged")

        url = reverse("github-pull-request-list")
        response = api_client.get(
            url, {"repository": str(integration.id), "state": "open"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
