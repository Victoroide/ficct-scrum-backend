"""
Unit tests for RAG service.

CRITICAL: All external API calls (Azure OpenAI, Pinecone) are mocked.
NO real API calls are made during tests.
"""

import pytest
from unittest.mock import MagicMock, patch, call
import hashlib

from apps.ai_assistant.services import RAGService
from apps.ai_assistant.models import IssueEmbedding
from apps.ai_assistant.tests.factories import IssueEmbeddingFactory
from apps.projects.tests.factories import IssueFactory, ProjectFactory


# Mock embedding vector (1536 dimensions)
MOCK_EMBEDDING = [0.1] * 1536


@pytest.mark.django_db
class TestRAGService:
    """Test RAGService methods with mocked external APIs."""

    def setup_method(self):
        """Set up test data and mocks."""
        self.service = RAGService()
        self.project = ProjectFactory()

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_index_issue_new(self, mock_pinecone_service, mock_openai_service):
        """Test indexing a new issue."""
        # Setup mocks
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = MOCK_EMBEDDING
        mock_openai_service.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.upsert.return_value = True
        mock_pinecone_service.return_value = mock_pinecone

        # Create issue
        issue = IssueFactory(
            project=self.project,
            title="Test issue",
            description="Test description",
        )

        # Index issue
        result = self.service.index_issue(str(issue.id))

        # Assertions
        assert result is True
        mock_openai.generate_embedding.assert_called_once()
        mock_pinecone.upsert.assert_called_once()

        # Verify embedding record created
        embedding = IssueEmbedding.objects.filter(issue=issue).first()
        assert embedding is not None
        assert embedding.vector_id == f"issue_{issue.id}"

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_index_issue_already_indexed_no_change(
        self, mock_pinecone_service, mock_openai_service
    ):
        """Test reindexing an issue with unchanged content."""
        mock_openai = MagicMock()
        mock_openai_service.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone_service.return_value = mock_pinecone

        # Create issue with existing embedding
        issue = IssueFactory(
            project=self.project,
            title="Test issue",
            description="Test description",
        )

        content = f"{issue.title} {issue.description or ''}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        IssueEmbeddingFactory(
            issue=issue,
            content_hash=content_hash,
        )

        # Try to reindex (should skip)
        result = self.service.index_issue(str(issue.id), force_reindex=False)

        # Should not call OpenAI or Pinecone since content unchanged
        mock_openai.generate_embedding.assert_not_called()
        mock_pinecone.upsert.assert_not_called()

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_index_issue_force_reindex(
        self, mock_pinecone_service, mock_openai_service
    ):
        """Test force reindexing an issue."""
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = MOCK_EMBEDDING
        mock_openai_service.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.upsert.return_value = True
        mock_pinecone_service.return_value = mock_pinecone

        issue = IssueFactory(project=self.project)
        IssueEmbeddingFactory(issue=issue)

        # Force reindex
        result = self.service.index_issue(str(issue.id), force_reindex=True)

        # Should call APIs even though already indexed
        assert result is True
        mock_openai.generate_embedding.assert_called_once()
        mock_pinecone.upsert.assert_called_once()

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_semantic_search(self, mock_pinecone_service, mock_openai_service):
        """Test semantic search functionality."""
        # Setup mocks
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = MOCK_EMBEDDING
        mock_openai_service.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = [
            {
                "id": "issue_uuid1",
                "score": 0.95,
                "metadata": {
                    "title": "Authentication bug",
                    "project_id": str(self.project.id),
                },
            },
            {
                "id": "issue_uuid2",
                "score": 0.88,
                "metadata": {
                    "title": "Login issue",
                    "project_id": str(self.project.id),
                },
            },
        ]
        mock_pinecone_service.return_value = mock_pinecone

        # Perform search
        results = self.service.semantic_search(
            query="authentication problems",
            project_id=str(self.project.id),
            top_k=5,
        )

        # Assertions
        assert len(results) == 2
        assert results[0]["similarity_score"] == 0.95
        assert results[0]["title"] == "Authentication bug"

        mock_openai.generate_embedding.assert_called_once_with("authentication problems")
        mock_pinecone.query.assert_called_once()

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_find_similar_issues(self, mock_pinecone_service, mock_openai_service):
        """Test finding similar issues."""
        mock_openai = MagicMock()
        mock_openai_service.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = [
            {
                "id": "issue_similar1",
                "score": 0.92,
                "metadata": {"title": "Similar issue", "project_id": str(self.project.id)},
            }
        ]
        mock_pinecone_service.return_value = mock_pinecone

        # Create issue with embedding
        issue = IssueFactory(project=self.project)
        IssueEmbeddingFactory(issue=issue, vector_id=f"issue_{issue.id}")

        # Find similar
        results = self.service.find_similar_issues(
            issue_id=str(issue.id),
            top_k=5,
            same_project_only=True,
        )

        # Assertions
        assert isinstance(results, list)
        mock_pinecone.query.assert_called_once()

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_delete_issue_embedding(self, mock_pinecone_service):
        """Test deleting issue from vector index."""
        mock_pinecone = MagicMock()
        mock_pinecone.delete.return_value = True
        mock_pinecone_service.return_value = mock_pinecone

        issue = IssueFactory(project=self.project)
        embedding = IssueEmbeddingFactory(issue=issue)

        # Delete embedding
        result = self.service.delete_issue_embedding(str(issue.id))

        # Assertions
        assert result is True
        mock_pinecone.delete.assert_called_once_with(f"issue_{issue.id}")

        # Verify database record deleted
        assert not IssueEmbedding.objects.filter(id=embedding.id).exists()

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    def test_index_project_issues_batch(
        self, mock_pinecone_service, mock_openai_service
    ):
        """Test batch indexing of project issues."""
        # Setup mocks
        mock_openai = MagicMock()
        mock_openai.generate_embedding_batch.return_value = [MOCK_EMBEDDING] * 3
        mock_openai_service.return_value = mock_openai

        mock_pinecone = MagicMock()
        mock_pinecone.upsert_batch.return_value = True
        mock_pinecone_service.return_value = mock_pinecone

        # Create issues
        for i in range(3):
            IssueFactory(project=self.project, title=f"Issue {i}")

        # Batch index
        result = self.service.index_project_issues(
            project_id=str(self.project.id),
            batch_size=50,
        )

        # Assertions
        assert result["total"] == 3
        assert result["indexed"] == 3
        assert result["failed"] == 0
        mock_pinecone.upsert_batch.assert_called()


@pytest.mark.django_db
class TestRAGServiceErrorHandling:
    """Test error handling in RAG service."""

    def setup_method(self):
        """Set up test data."""
        self.service = RAGService()

    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_index_issue_openai_error(self, mock_openai_service):
        """Test handling of Azure OpenAI errors."""
        mock_openai = MagicMock()
        mock_openai.generate_embedding.side_effect = Exception("API Error")
        mock_openai_service.return_value = mock_openai

        issue = IssueFactory()

        # Should handle error gracefully
        result = self.service.index_issue(str(issue.id))
        assert result is False

    def test_semantic_search_with_empty_query(self):
        """Test search with empty query."""
        with pytest.raises(ValueError):
            self.service.semantic_search(query="", project_id="test-uuid")

    def test_find_similar_issues_nonexistent_issue(self):
        """Test finding similar issues for non-existent issue."""
        result = self.service.find_similar_issues(
            issue_id="00000000-0000-0000-0000-000000000000"
        )

        # Should return empty list
        assert result == []
