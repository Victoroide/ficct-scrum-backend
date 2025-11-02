"""
API endpoint tests for AI Assistant features.

All external API calls (OpenAI, Pinecone) are mocked.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.authentication.tests.factories import UserFactory
from apps.projects.tests.factories import ProjectFactory, IssueFactory, SprintFactory
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


MOCK_EMBEDDING = [0.1] * 1536


@pytest.mark.django_db
class TestRAGIndexingEndpoints:
    """Test RAG indexing API endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        self.issue = IssueFactory(project=self.project)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_index_issue_success(self, mock_pinecone_svc, mock_openai_svc, api_client):
        """Test indexing a single issue."""
        # Setup mocks
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = MOCK_EMBEDDING
        mock_openai_svc.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.upsert.return_value = True
        mock_pinecone_svc.return_value = mock_pinecone

        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-index-issue", kwargs={"pk": self.issue.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert "status" in response.data

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_index_project_issues(
        self, mock_pinecone_svc, mock_openai_svc, api_client
    ):
        """Test batch indexing project issues."""
        mock_openai = MagicMock()
        mock_openai.generate_embedding_batch.return_value = [MOCK_EMBEDDING] * 5
        mock_openai_svc.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.upsert_batch.return_value = True
        mock_pinecone_svc.return_value = mock_pinecone

        # Create issues
        IssueFactory.create_batch(5, project=self.project)

        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-index-project", kwargs={"pk": self.project.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert "total" in response.data

    def test_index_requires_authentication(self, api_client):
        """Test indexing requires authentication."""
        url = reverse("ai-assistant-index-issue", kwargs={"pk": self.issue.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRAGSearchEndpoints:
    """Test RAG search API endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_search_issues(self, mock_pinecone_svc, mock_openai_svc, api_client):
        """Test semantic search for issues."""
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = MOCK_EMBEDDING
        mock_openai_svc.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = [
            {
                "id": "issue_123",
                "score": 0.95,
                "metadata": {"title": "Test issue", "project_id": str(self.project.id)},
            }
        ]
        mock_pinecone_svc.return_value = mock_pinecone

        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "authentication problems",
            "project_id": str(self.project.id),
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_search_missing_query(self, api_client):
        """Test search with missing query."""
        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-search-issues")
        data = {"project_id": str(self.project.id)}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAIAssistantEndpoints:
    """Test AI assistant query endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    @patch("apps.ai_assistant.services.assistant_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_query_assistant(self, mock_pinecone_svc, mock_openai_svc, api_client):
        """Test querying AI assistant."""
        mock_openai = MagicMock()
        mock_openai.chat_completion.return_value = "This is the answer"
        mock_openai_svc.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = []
        mock_pinecone_svc.return_value = mock_pinecone

        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-query")
        data = {
            "question": "How do I create an issue?",
            "project_id": str(self.project.id),
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]


@pytest.mark.django_db
class TestSummarizationEndpoints:
    """Test summarization API endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        self.issue = IssueFactory(project=self.project)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    @patch("apps.ai_assistant.services.summarization_service.get_azure_openai_service")
    def test_summarize_issue(self, mock_openai_svc, api_client):
        """Test issue summarization."""
        mock_openai = MagicMock()
        mock_openai.chat_completion.return_value = "Summary of the issue"
        mock_openai_svc.return_value = mock_openai

        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-summarize-issue", kwargs={"pk": self.issue.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert "summary" in response.data

    @patch("apps.ai_assistant.services.summarization_service.get_azure_openai_service")
    def test_summarize_sprint(self, mock_openai_svc, api_client):
        """Test sprint summarization."""
        mock_openai = MagicMock()
        mock_openai.chat_completion.return_value = "Summary of the sprint"
        mock_openai_svc.return_value = mock_openai

        sprint = SprintFactory(project=self.project)

        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-summarize-sprint", kwargs={"pk": sprint.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert "summary" in response.data


@pytest.mark.django_db
class TestSimilarIssuesEndpoint:
    """Test similar issues endpoint."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        self.issue = IssueFactory(project=self.project)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_find_similar_issues(self, mock_pinecone_svc, api_client):
        """Test finding similar issues."""
        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = [
            {
                "id": "issue_similar",
                "score": 0.92,
                "metadata": {"title": "Similar issue"},
            }
        ]
        mock_pinecone_svc.return_value = mock_pinecone

        api_client.force_authenticate(user=self.user)

        url = reverse("ai-assistant-similar-issues", kwargs={"pk": self.issue.id})
        response = api_client.get(url)

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        ]


@pytest.mark.django_db
class TestAIAssistantPermissions:
    """Test AI assistant permissions."""

    def test_unauthenticated_access_denied(self, api_client):
        """Test unauthenticated users cannot access AI endpoints."""
        issue = IssueFactory()

        url = reverse("ai-assistant-index-issue", kwargs={"pk": issue.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_member_access_denied(self, api_client):
        """Test non-project members cannot access AI features."""
        user = UserFactory()
        issue = IssueFactory()

        api_client.force_authenticate(user=user)

        url = reverse("ai-assistant-index-issue", kwargs={"pk": issue.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
