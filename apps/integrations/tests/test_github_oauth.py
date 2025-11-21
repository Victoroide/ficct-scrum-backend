"""
Integration tests for GitHub OAuth flow and permissions.

Tests cover:
- OAuth initiation and callback flow
- Permission checks (project owner/admin, workspace admin, org owner/admin)
- Error handling (missing fields, invalid permissions)
- Direct creation endpoint validation
"""

from unittest.mock import Mock, patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from rest_framework import status
from rest_framework.test import APIClient

from apps.integrations.models import GitHubIntegration
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectTeamMember
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMember


class GitHubOAuthFlowTestCase(TestCase):
    """Test GitHub OAuth initiation and callback flow"""

    def setUp(self):
        self.factory = RequestFactory()
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
        self.owner_user = User.objects.create_user(
            email="owner@test.com", username="owner", password="testpass123"
        )
        self.member_user = User.objects.create_user(
            email="member@test.com", username="member", password="testpass123"
        )
        self.external_user = User.objects.create_user(
            email="external@test.com", username="external", password="testpass123"
        )

        # Set up permissions
        ProjectTeamMember.objects.create(
            project=self.project, user=self.owner_user, role="owner", is_active=True
        )
        ProjectTeamMember.objects.create(
            project=self.project, user=self.member_user, role="member", is_active=True
        )

    def test_initiate_oauth_success(self):
        """Test successful OAuth initiation"""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.post(
            "/api/v1/integrations/github/oauth/initiate/",
            {"project": str(self.project.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("authorization_url", response.data)
        self.assertIn("state", response.data)
        self.assertIn(
            "github.com/login/oauth/authorize", response.data["authorization_url"]
        )

    def test_initiate_oauth_missing_project(self):
        """Test OAuth initiation fails when project is missing"""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.post(
            "/api/v1/integrations/github/oauth/initiate/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("project", response.data["error"].lower())

    def test_initiate_oauth_invalid_project(self):
        """Test OAuth initiation fails with non-existent project"""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.post(
            "/api/v1/integrations/github/oauth/initiate/",
            {"project": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )

        # Should fail due to permission check (project doesn't exist)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_initiate_oauth_no_permission(self):
        """Test OAuth initiation fails when user has no permissions"""
        self.client.force_authenticate(user=self.external_user)

        response = self.client.post(
            "/api/v1/integrations/github/oauth/initiate/",
            {"project": str(self.project.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.integrations.viewsets.github_integration_viewset.requests.post")
    @patch("apps.integrations.viewsets.github_integration_viewset.Github")
    def test_oauth_callback_success(self, mock_github, mock_post):
        """Test successful OAuth callback"""
        # Mock GitHub API responses
        mock_token_response = Mock()
        mock_token_response.json.return_value = {"access_token": "test_access_token"}
        mock_post.return_value = mock_token_response

        # Mock GitHub user and repo
        mock_repo = Mock()
        mock_repo.html_url = "https://github.com/test/repo"
        mock_repo.full_name = "test/repo"

        mock_user = Mock()
        mock_user.get_repos.return_value = [mock_repo]

        mock_gh_instance = Mock()
        mock_gh_instance.get_user.return_value = mock_user
        mock_github.return_value = mock_gh_instance

        # Set up session
        request = self.factory.get("/api/v1/integrations/github/oauth/callback/")
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session["github_oauth_state"] = "test_state"
        request.session["github_oauth_project"] = str(self.project.id)
        request.session["github_oauth_user"] = str(self.owner_user.id)
        request.session.save()

        # Make callback request
        response = self.client.get(
            "/api/v1/integrations/github/oauth/callback/",
            {"code": "test_code", "state": "test_state"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertIn("integration_id", response.data)

        # Verify integration was created
        self.assertTrue(GitHubIntegration.objects.filter(project=self.project).exists())

    def test_oauth_callback_invalid_state(self):
        """Test OAuth callback fails with invalid state"""
        request = self.factory.get("/api/v1/integrations/github/oauth/callback/")
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session["github_oauth_state"] = "correct_state"
        request.session.save()

        response = self.client.get(
            "/api/v1/integrations/github/oauth/callback/",
            {"code": "test_code", "state": "wrong_state"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)


class GitHubIntegrationPermissionsTestCase(TestCase):
    """Test permission checks for GitHub integration management"""

    def setUp(self):
        self.factory = RequestFactory()
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
        self.project_owner = User.objects.create_user(
            email="project_owner@test.com",
            username="project_owner",
            password="testpass123",
        )
        self.workspace_admin = User.objects.create_user(
            email="workspace_admin@test.com",
            username="workspace_admin",
            password="testpass123",
        )
        self.org_owner = User.objects.create_user(
            email="org_owner@test.com", username="org_owner", password="testpass123"
        )
        self.regular_member = User.objects.create_user(
            email="member@test.com", username="member", password="testpass123"
        )
        self.external_user = User.objects.create_user(
            email="external@test.com", username="external", password="testpass123"
        )

        # Set up permissions
        ProjectTeamMember.objects.create(
            project=self.project, user=self.project_owner, role="owner", is_active=True
        )
        ProjectTeamMember.objects.create(
            project=self.project,
            user=self.regular_member,
            role="member",
            is_active=True,
        )
        WorkspaceMember.objects.create(
            workspace=self.workspace,
            user=self.workspace_admin,
            role="admin",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.org_owner,
            role="owner",
            is_active=True,
        )

    def test_project_owner_can_create(self):
        """Test project owner can create GitHub integration"""
        self.client.force_authenticate(user=self.project_owner)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": str(self.project.id),
                "repository_url": "https://github.com/test/repo",
                "access_token": "test_token",
            },
            format="json",
        )

        # Will fail at service level but permissions should pass
        # 403 means permission denied, anything else means permissions passed
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_workspace_admin_can_create(self):
        """Test workspace admin can create GitHub integration"""
        self.client.force_authenticate(user=self.workspace_admin)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": str(self.project.id),
                "repository_url": "https://github.com/test/repo",
                "access_token": "test_token",
            },
            format="json",
        )

        # Permissions should pass (not 403)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_org_owner_can_create(self):
        """Test organization owner can create GitHub integration"""
        self.client.force_authenticate(user=self.org_owner)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": str(self.project.id),
                "repository_url": "https://github.com/test/repo",
                "access_token": "test_token",
            },
            format="json",
        )

        # Permissions should pass (not 403)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_member_cannot_create(self):
        """Test regular project member cannot create GitHub integration"""
        self.client.force_authenticate(user=self.regular_member)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": str(self.project.id),
                "repository_url": "https://github.com/test/repo",
                "access_token": "test_token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("permission", response.data["detail"].lower())

    def test_external_user_cannot_create(self):
        """Test external user cannot create GitHub integration"""
        self.client.force_authenticate(user=self.external_user)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": str(self.project.id),
                "repository_url": "https://github.com/test/repo",
                "access_token": "test_token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GitHubIntegrationValidationTestCase(TestCase):
    """Test serializer validation for GitHub integration creation"""

    def setUp(self):
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

        # Create user
        self.owner_user = User.objects.create_user(
            email="owner@test.com", username="owner", password="testpass123"
        )

        ProjectTeamMember.objects.create(
            project=self.project, user=self.owner_user, role="owner", is_active=True
        )

    def test_create_without_project_returns_403(self):
        """Test creating integration without project field returns 403 with clear message"""  # noqa: E501
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "repository_url": "https://github.com/test/repo",
                "access_token": "test_token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("project", response.data["detail"].lower())
        self.assertIn("missing", response.data["detail"].lower())

    def test_create_without_access_token_returns_400(self):
        """Test creating integration without access_token returns 400 with clear message"""  # noqa: E501
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": str(self.project.id),
                "repository_url": "https://github.com/test/repo",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("access_token", response.data)
        self.assertIn("oauth", response.data["access_token"][0].lower())

    def test_create_with_invalid_repository_url_returns_400(self):
        """Test creating integration with invalid repository URL returns 400"""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": str(self.project.id),
                "repository_url": "https://gitlab.com/test/repo",  # Not GitHub
                "access_token": "test_token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("repository_url", response.data)

    def test_create_with_nonexistent_project_returns_403(self):
        """Test creating integration with non-existent project returns 403 with clear message"""  # noqa: E501
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.post(
            "/api/v1/integrations/github/",
            {
                "project": "00000000-0000-0000-0000-000000000000",
                "repository_url": "https://github.com/test/repo",
                "access_token": "test_token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("does not exist", response.data["detail"])


class GitHubIntegrationListTestCase(TestCase):
    """Test listing GitHub integrations"""

    def setUp(self):
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

        # Create projects
        self.project1 = Project.objects.create(
            name="Project 1",
            key="PROJ1",
            workspace=self.workspace,
        )
        self.project2 = Project.objects.create(
            name="Project 2",
            key="PROJ2",
            workspace=self.workspace,
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@test.com", username="user", password="testpass123"
        )

        ProjectTeamMember.objects.create(
            project=self.project1, user=self.user, role="member", is_active=True
        )

        # Create integrations
        self.integration1 = GitHubIntegration.objects.create(
            project=self.project1,
            repository_url="https://github.com/test/repo1",
            repository_owner="test",
            repository_name="repo1",
            access_token=b"encrypted_token",
        )

    def test_list_integrations(self):
        """Test listing GitHub integrations"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/integrations/github/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_project(self):
        """Test filtering integrations by project"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/integrations/github/?project={self.project1.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
