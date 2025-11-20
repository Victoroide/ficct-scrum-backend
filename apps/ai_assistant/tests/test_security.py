"""
Security tests for AI Assistant to prevent cross-project data leakage.

These tests verify that the AI Assistant properly enforces project-level
access control and prevents unauthorized users from accessing data from
projects they don't belong to.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from unittest.mock import MagicMock, patch

from apps.projects.models import Project, ProjectTeamMember
from apps.workspaces.models import Workspace, WorkspaceMember
from tests.factories import IssueFactory, ProjectFactory, UserFactory, WorkspaceFactory


@pytest.mark.django_db
class TestAISecurityIsolation:
    """Test AI Assistant respects project data isolation."""
    
    def setup_method(self):
        """Set up test data with two isolated projects."""
        # User Alice - member of Project A only
        self.alice = UserFactory(username="alice", email="alice@test.com")
        
        # User Bob - member of Project B only
        self.bob = UserFactory(username="bob", email="bob@test.com")
        
        # Workspace with two projects
        self.workspace = WorkspaceFactory(name="Test Workspace")
        
        # Project A - Alice is member
        self.project_a = ProjectFactory(
            workspace=self.workspace,
            name="Project A",
            key="PROJA"
        )
        ProjectTeamMember.objects.create(
            project=self.project_a,
            user=self.alice,
            role="member",
            is_active=True
        )
        
        # Project B - Bob is member
        self.project_b = ProjectFactory(
            workspace=self.workspace,
            name="Project B",
            key="PROJB"
        )
        ProjectTeamMember.objects.create(
            project=self.project_b,
            user=self.bob,
            role="member",
            is_active=True
        )
        
        # Create issues in each project
        self.issue_a = IssueFactory(
            project=self.project_a,
            title="Secret issue in Project A",
            description="Confidential information about Project A"
        )
        self.issue_b = IssueFactory(
            project=self.project_b,
            title="Confidential issue in Project B",
            description="Secret data about Project B"
        )
    
    def test_cannot_search_unauthorized_project(self, api_client):
        """
        CRITICAL: User cannot search issues in project they don't have access to.
        
        Attack scenario:
        - Alice is member of Project A
        - Alice tries to search Project B by specifying its project_id
        - Should be FORBIDDEN (403)
        """
        api_client.force_authenticate(user=self.alice)
        
        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "show me all issues",
            "project_id": str(self.project_b.id),  # ← Alice tries to access Bob's project
        }
        
        response = api_client.post(url, data, format="json")
        
        # Should be forbidden
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "access" in response.data["error"].lower()
    
    def test_cannot_query_assistant_for_unauthorized_project(self, api_client):
        """
        CRITICAL: User cannot query AI assistant about unauthorized project.
        
        Attack scenario:
        - Alice tries to ask AI questions about Project B
        - Should be FORBIDDEN (403)
        """
        api_client.force_authenticate(user=self.alice)
        
        url = reverse("ai-assistant-query")
        data = {
            "question": "What are the critical bugs?",
            "project_id": str(self.project_b.id),  # ← Unauthorized
        }
        
        response = api_client.post(url, data, format="json")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "access" in response.data["error"].lower()
    
    def test_cannot_suggest_solutions_for_unauthorized_project(self, api_client):
        """
        CRITICAL: User cannot get solution suggestions for unauthorized project.
        
        Attack scenario:
        - Alice tries to get solutions based on Project B's history
        - Should be FORBIDDEN (403)
        """
        api_client.force_authenticate(user=self.alice)
        
        url = reverse("ai-assistant-suggest-solutions")
        data = {
            "issue_description": "How to fix authentication bug?",
            "project_id": str(self.project_b.id),  # ← Unauthorized
        }
        
        response = api_client.post(url, data, format="json")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "access" in response.data["error"].lower()
    
    def test_authorized_search_succeeds(self, api_client):
        """User CAN search their own project."""
        api_client.force_authenticate(user=self.alice)
        
        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "test query",
            "project_id": str(self.project_a.id),  # ← Alice's own project
        }
        
        with patch('apps.ai_assistant.services.rag_service.get_pinecone_service'):
            with patch('apps.ai_assistant.services.rag_service.get_azure_openai_service'):
                response = api_client.post(url, data, format="json")
        
        # Should succeed (200) or fail for other reasons (503 if service unavailable)
        # But NOT 403 Forbidden
        assert response.status_code != status.HTTP_403_FORBIDDEN
    
    def test_workspace_member_can_access_all_projects(self, api_client):
        """
        Workspace members can access all projects in their workspace.
        
        Scenario:
        - Admin is workspace member (not specific project member)
        - Admin should be able to search both Project A and Project B
        """
        # Create workspace admin
        admin = UserFactory(username="admin", email="admin@test.com")
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=admin,
            role="admin",
            is_active=True
        )
        
        api_client.force_authenticate(user=admin)
        url = reverse("ai-assistant-search-issues")
        
        # Admin can search Project A
        data_a = {
            "query": "test",
            "project_id": str(self.project_a.id)
        }
        
        with patch('apps.ai_assistant.services.rag_service.get_pinecone_service'):
            with patch('apps.ai_assistant.services.rag_service.get_azure_openai_service'):
                response_a = api_client.post(url, data_a, format="json")
        
        assert response_a.status_code != status.HTTP_403_FORBIDDEN
        
        # Admin can also search Project B
        data_b = {
            "query": "test",
            "project_id": str(self.project_b.id)
        }
        
        with patch('apps.ai_assistant.services.rag_service.get_pinecone_service'):
            with patch('apps.ai_assistant.services.rag_service.get_azure_openai_service'):
                response_b = api_client.post(url, data_b, format="json")
        
        assert response_b.status_code != status.HTTP_403_FORBIDDEN
    
    def test_nonexistent_project_returns_404(self, api_client):
        """Querying a non-existent project returns 404."""
        api_client.force_authenticate(user=self.alice)
        
        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "test",
            "project_id": "00000000-0000-0000-0000-000000000000",  # Non-existent
        }
        
        response = api_client.post(url, data, format="json")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"].lower()
    
    def test_unauthenticated_request_is_rejected(self, api_client):
        """Unauthenticated requests are rejected."""
        # No authentication
        
        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "test",
            "project_id": str(self.project_a.id),
        }
        
        response = api_client.post(url, data, format="json")
        
        # Should be 401 Unauthorized or 403 Forbidden
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]


@pytest.mark.django_db
class TestPineconeFilterSecurity:
    """Test that Pinecone queries use proper project filtering."""
    
    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        ProjectTeamMember.objects.create(
            project=self.project,
            user=self.user,
            role="member",
            is_active=True
        )
    
    @patch('apps.ai_assistant.services.rag_service.get_pinecone_service')
    @patch('apps.ai_assistant.services.rag_service.get_azure_openai_service')
    def test_pinecone_query_includes_project_filter(
        self, mock_openai_service, mock_pinecone_service
    ):
        """
        Verify that Pinecone queries include project_id filter.
        
        This ensures database-level isolation.
        """
        from apps.ai_assistant.services.rag_service import RAGService
        
        # Mock services
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = [0.1] * 1536
        mock_openai_service.return_value = mock_openai
        
        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = []
        mock_pinecone_service.return_value = mock_pinecone
        
        # Create RAG service and search
        rag = RAGService()
        rag.available = True
        
        project_id = str(self.project.id)
        rag.semantic_search(
            query="test query",
            project_id=project_id,
            top_k=10
        )
        
        # Verify Pinecone query was called with project filter
        mock_pinecone.query.assert_called_once()
        call_kwargs = mock_pinecone.query.call_args[1]
        
        # Check that filter_dict includes project_id
        assert call_kwargs.get('filter_dict') is not None
        filter_dict = call_kwargs['filter_dict']
        assert 'project_id' in filter_dict
        assert filter_dict['project_id']['$eq'] == project_id
    
    @patch('apps.ai_assistant.services.rag_service.get_pinecone_service')
    @patch('apps.ai_assistant.services.rag_service.get_azure_openai_service')
    def test_pinecone_filter_combines_with_custom_filters(
        self, mock_openai_service, mock_pinecone_service
    ):
        """
        Verify that project filter is combined with custom filters using $and.
        """
        from apps.ai_assistant.services.rag_service import RAGService
        
        # Mock services
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = [0.1] * 1536
        mock_openai_service.return_value = mock_openai
        
        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = []
        mock_pinecone_service.return_value = mock_pinecone
        
        # Create RAG service and search with custom filters
        rag = RAGService()
        rag.available = True
        
        project_id = str(self.project.id)
        rag.semantic_search(
            query="test query",
            project_id=project_id,
            top_k=10,
            filters={"status": "Done"}  # Custom filter
        )
        
        # Verify filter uses $and to combine
        call_kwargs = mock_pinecone.query.call_args[1]
        filter_dict = call_kwargs['filter_dict']
        
        # Should have $and combining project filter and status filter
        assert '$and' in filter_dict
        filters_list = filter_dict['$and']
        assert len(filters_list) == 2
        
        # Check project filter is present
        project_filters = [f for f in filters_list if 'project_id' in f]
        assert len(project_filters) == 1
        assert project_filters[0]['project_id']['$eq'] == project_id


@pytest.mark.django_db
class TestSecurityLogging:
    """Test that security events are properly logged."""
    
    def setup_method(self):
        """Set up test data."""
        self.alice = UserFactory(username="alice")
        self.bob = UserFactory(username="bob")
        
        self.workspace = WorkspaceFactory()
        self.project_a = ProjectFactory(workspace=self.workspace)
        self.project_b = ProjectFactory(workspace=self.workspace)
        
        ProjectTeamMember.objects.create(
            project=self.project_a,
            user=self.alice,
            role="member",
            is_active=True
        )
    
    def test_unauthorized_access_attempt_is_logged(self, api_client, caplog):
        """
        Verify that unauthorized access attempts are logged.
        
        This is important for security auditing and breach detection.
        """
        import logging
        caplog.set_level(logging.WARNING)
        
        api_client.force_authenticate(user=self.alice)
        
        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "test",
            "project_id": str(self.project_b.id),  # Unauthorized
        }
        
        response = api_client.post(url, data, format="json")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Check that security warning was logged
        security_logs = [r for r in caplog.records if "SECURITY" in r.message]
        assert len(security_logs) > 0
        
        # Verify log contains user and project info
        log_message = security_logs[0].message
        assert str(self.alice.id) in log_message
        assert str(self.project_b.id) in log_message


@pytest.mark.django_db
class TestDefenseInDepth:
    """Test defense-in-depth validation layers."""
    
    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        ProjectTeamMember.objects.create(
            project=self.project,
            user=self.user,
            role="member",
            is_active=True
        )
    
    @patch('apps.ai_assistant.services.rag_service.get_pinecone_service')
    @patch('apps.ai_assistant.services.rag_service.get_azure_openai_service')
    def test_validation_layer_detects_filter_bypass(
        self, mock_openai_service, mock_pinecone_service, caplog
    ):
        """
        Test that validation layer detects if Pinecone filter is bypassed.
        
        Scenario: Pinecone returns results from wrong project (filter malfunction)
        Expected: Validation layer catches this and logs security violation
        """
        import logging
        caplog.set_level(logging.ERROR)
        
        from apps.ai_assistant.services.rag_service import RAGService
        
        # Mock services
        mock_openai = MagicMock()
        mock_openai.generate_embedding.return_value = [0.1] * 1536
        mock_openai_service.return_value = mock_openai
        
        # Mock Pinecone to return result from WRONG project (simulating filter bypass)
        mock_pinecone = MagicMock()
        mock_pinecone.query.return_value = [
            {
                "id": "issue_wrong_project",
                "score": 0.95,
                "metadata": {
                    "issue_id": "12345",
                    "project_id": "wrong-project-id",  # ← Wrong project!
                }
            }
        ]
        mock_pinecone_service.return_value = mock_pinecone
        
        # Create RAG service and search
        rag = RAGService()
        rag.available = True
        
        results = rag.semantic_search(
            query="test query",
            project_id=str(self.project.id),  # Searching for this project
            top_k=10
        )
        
        # Should return empty results (validated out)
        assert len(results) == 0
        
        # Should log security violation
        security_logs = [r for r in caplog.records if "SECURITY VIOLATION" in r.message]
        assert len(security_logs) > 0


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        ProjectTeamMember.objects.create(
            project=self.project,
            user=self.user,
            role="member",
            is_active=True
        )
    
    def test_search_without_project_id(self, api_client):
        """
        Search without project_id should work (searches all accessible projects).
        
        This is a legitimate use case for cross-project search by authorized users.
        """
        api_client.force_authenticate(user=self.user)
        
        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "test query",
            # No project_id
        }
        
        with patch('apps.ai_assistant.services.rag_service.get_pinecone_service'):
            with patch('apps.ai_assistant.services.rag_service.get_azure_openai_service'):
                response = api_client.post(url, data, format="json")
        
        # Should not be forbidden (can search across all accessible projects)
        assert response.status_code != status.HTTP_403_FORBIDDEN
    
    def test_invalid_project_id_format(self, api_client):
        """Invalid UUID format should be handled gracefully."""
        api_client.force_authenticate(user=self.user)
        
        url = reverse("ai-assistant-search-issues")
        data = {
            "query": "test",
            "project_id": "invalid-uuid-format",
        }
        
        response = api_client.post(url, data, format="json")
        
        # Should return 404 (not found) or 400 (bad request)
        # But NOT allow search to proceed
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]
