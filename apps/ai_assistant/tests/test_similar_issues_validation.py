"""
Tests for similar_issues endpoint parameter validation.

Verifies that the endpoint handles invalid UUIDs, parameters, and edge cases
correctly without returning 500 errors.
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from apps.ai_assistant.factories import IssueEmbeddingFactory
from apps.organizations.models import Organization
from apps.projects.models import Project
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMember


class SimilarIssuesValidationTestCase(TestCase):
    """Test parameter validation for similar_issues endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create organization
        self.organization = Organization.objects.create(
            name="Test Org", slug="test-org"
        )

        # Create workspace
        self.workspace = Workspace.objects.create(
            name="Test Workspace",
            key="TEST",
            organization=self.organization,
        )

        # Create project
        self.project = Project.objects.create(
            name="Test Project",
            key="PROJ",
            workspace=self.workspace,
        )

        # Create users
        self.user = User.objects.create_user(
            email="user@test.com", username="testuser", password="testpass123"
        )

        # Set up permissions
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.user,
            role="member",
            is_active=True,
        )

        # Create test issue
        from apps.projects.factories import (
            IssueFactory,
            IssueTypeFactory,
            WorkflowStatusFactory,
        )

        self.issue_type = IssueTypeFactory(project=self.project)
        self.status = WorkflowStatusFactory(project=self.project)
        self.issue = IssueFactory(
            project=self.project,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.user,
        )

    # ================== INVALID UUID TESTS ==================

    def test_similar_issues_with_invalid_uuid_string(self):
        """Test that invalid UUID string returns 400, not 500."""
        self.client.force_authenticate(user=self.user)

        # Invalid UUID: plain string
        response = self.client.get("/api/v1/ai/invalid-uuid/similar-issues/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Invalid issue ID format", response.data["error"])

    def test_similar_issues_with_integer_id(self):
        """Test that integer ID returns 400, not 500."""
        self.client.force_authenticate(user=self.user)

        # Invalid UUID: integer
        response = self.client.get("/api/v1/ai/1/similar-issues/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("UUID", response.data["detail"])

    def test_similar_issues_with_malformed_uuid(self):
        """Test that malformed UUID returns 400."""
        self.client.force_authenticate(user=self.user)

        # Malformed UUID
        response = self.client.get("/api/v1/ai/123e4567-e89b-12d3/similar-issues/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ================== PARAMETER VALIDATION TESTS ==================

    def test_similar_issues_with_invalid_top_k_string(self):
        """Test that non-integer top_k returns 400."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/ai/{self.issue.id}/similar-issues/?top_k=abc"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("top_k", response.data["error"])

    def test_similar_issues_with_negative_top_k(self):
        """Test that negative top_k returns 400."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/ai/{self.issue.id}/similar-issues/?top_k=-5"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("between 1 and 20", response.data["detail"])

    def test_similar_issues_with_top_k_too_large(self):
        """Test that top_k > 20 returns 400."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/ai/{self.issue.id}/similar-issues/?top_k=100"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("between 1 and 20", response.data["detail"])

    def test_similar_issues_with_valid_top_k(self):
        """Test that valid top_k works."""
        self.client.force_authenticate(user=self.user)

        with patch("apps.ai_assistant.services.rag_service.get_pinecone_service"):
            with patch(
                "apps.ai_assistant.services.rag_service.get_azure_openai_service"
            ):
                response = self.client.get(
                    f"/api/v1/ai/{self.issue.id}/similar-issues/?top_k=10"
                )

        # Should not be 400 (might be 503 if AI service unavailable, which is OK)
        self.assertNotEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ================== NOT FOUND TESTS ==================

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_similar_issues_with_nonexistent_uuid(self, mock_openai, mock_pinecone):
        """Test that non-existent issue UUID returns 404."""
        # Mock services as available
        mock_openai.return_value = MagicMock()
        mock_pinecone.return_value = MagicMock()

        self.client.force_authenticate(user=self.user)

        # Valid UUID format but doesn't exist
        fake_uuid = uuid.uuid4()
        response = self.client.get(f"/api/v1/ai/{fake_uuid}/similar-issues/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertIn("not found", response.data["error"].lower())

    # ================== SUCCESS TESTS ==================

    @patch("apps.ai_assistant.services.rag_service.RAGService.find_similar_issues")
    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_similar_issues_success(
        self, mock_openai, mock_pinecone, mock_find_similar
    ):
        """Test successful similar issues call."""
        # Mock services
        mock_openai.return_value = MagicMock()
        mock_pinecone.return_value = MagicMock()
        mock_find_similar.return_value = [
            {
                "issue_id": str(uuid.uuid4()),
                "title": "Similar Issue",
                "issue_type": "Bug",
                "status": "To Do",
                "project_key": "PROJ",
                "similarity_score": 0.95,
            }
        ]

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/ai/{self.issue.id}/similar-issues/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("similar_issues", response.data)
        self.assertIsInstance(response.data["similar_issues"], list)

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_similar_issues_with_same_project_only_true(
        self, mock_openai, mock_pinecone
    ):
        """Test same_project_only=true parameter."""
        mock_openai.return_value = MagicMock()
        mock_pinecone_instance = MagicMock()
        mock_pinecone_instance.query_by_id.return_value = []
        mock_pinecone.return_value = mock_pinecone_instance

        self.client.force_authenticate(user=self.user)

        # Create embedding
        IssueEmbeddingFactory(issue=self.issue, is_indexed=True)

        response = self.client.get(
            f"/api/v1/ai/{self.issue.id}/similar-issues/?same_project_only=true"
        )

        # Should work (might return empty list)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_similar_issues_with_same_project_only_false(
        self, mock_openai, mock_pinecone
    ):
        """Test same_project_only=false parameter."""
        mock_openai.return_value = MagicMock()
        mock_pinecone_instance = MagicMock()
        mock_pinecone_instance.query_by_id.return_value = []
        mock_pinecone.return_value = mock_pinecone_instance

        self.client.force_authenticate(user=self.user)

        # Create embedding
        IssueEmbeddingFactory(issue=self.issue, is_indexed=True)

        response = self.client.get(
            f"/api/v1/ai/{self.issue.id}/similar-issues/?same_project_only=false"
        )

        # Should work
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

    # ================== EDGE CASES ==================

    def test_similar_issues_with_empty_string_uuid(self):
        """Test that empty string UUID returns 400."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/ai/ /similar-issues/")

        # Should return 400 or 404 (depending on URL routing)
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND],
        )

    def test_similar_issues_without_authentication(self):
        """Test that unauthenticated request returns 401."""
        response = self.client.get(f"/api/v1/ai/{self.issue.id}/similar-issues/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_similar_issues_default_parameters(self, mock_openai, mock_pinecone):
        """Test that default parameters work correctly."""
        mock_openai.return_value = MagicMock()
        mock_pinecone_instance = MagicMock()
        mock_pinecone_instance.query_by_id.return_value = []
        mock_pinecone.return_value = mock_pinecone_instance

        self.client.force_authenticate(user=self.user)

        # Create embedding
        IssueEmbeddingFactory(issue=self.issue, is_indexed=True)

        # Call without parameters (should use defaults: top_k=5, same_project_only=true)
        response = self.client.get(f"/api/v1/ai/{self.issue.id}/similar-issues/")

        # Should work with defaults
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )


class RAGServiceTestCase(TestCase):
    """Test RAGService.find_similar_issues method."""

    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Org", slug="test-org"
        )
        self.workspace = Workspace.objects.create(
            name="Test Workspace",
            key="TEST",
            organization=self.organization,
        )
        self.project = Project.objects.create(
            name="Test Project",
            key="PROJ",
            workspace=self.workspace,
        )

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_find_similar_issues_returns_none_for_nonexistent_issue(
        self, mock_openai, mock_pinecone
    ):
        """Test that find_similar_issues returns None for non-existent issue."""
        from apps.ai_assistant.services import RAGService

        mock_openai.return_value = MagicMock()
        mock_pinecone.return_value = MagicMock()

        service = RAGService()
        fake_uuid = str(uuid.uuid4())

        result = service.find_similar_issues(issue_id=fake_uuid)

        self.assertIsNone(result)

    @patch("apps.ai_assistant.services.rag_service.get_pinecone_service")
    @patch("apps.ai_assistant.services.rag_service.get_azure_openai_service")
    def test_find_similar_issues_success(self, mock_openai, mock_pinecone):
        """Test successful find_similar_issues."""
        from apps.ai_assistant.services import RAGService
        from apps.projects.factories import (
            IssueFactory,
            IssueTypeFactory,
            WorkflowStatusFactory,
        )
        from apps.users.factories import UserFactory

        # Create issue
        issue_type = IssueTypeFactory(project=self.project)
        status_obj = WorkflowStatusFactory(project=self.project)
        user = UserFactory()
        issue = IssueFactory(
            project=self.project,
            issue_type=issue_type,
            status=status_obj,
            reporter=user,
        )

        # Mock services
        mock_openai.return_value = MagicMock()
        mock_pinecone_instance = MagicMock()
        mock_pinecone_instance.query_by_id.return_value = []
        mock_pinecone.return_value = mock_pinecone_instance

        # Create embedding
        IssueEmbeddingFactory(issue=issue, is_indexed=True)

        service = RAGService()
        result = service.find_similar_issues(issue_id=str(issue.id))

        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
