"""
Comprehensive tests for reporting endpoints.

Tests parameter validation, permission checks, and error handling
for all report and diagram endpoints.
"""
import uuid

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectTeamMember, Sprint
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMember


class ReportEndpointTestCase(TestCase):
    """Test report endpoints with comprehensive validation."""

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

        # Create sprint
        self.sprint = Sprint.objects.create(
            project=self.project,
            name="Sprint 1",
            goal="Test goal",
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

    # ================== VELOCITY ENDPOINT TESTS ==================

    def test_velocity_missing_project_parameter(self):
        """Test velocity endpoint without project parameter."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/reports/velocity/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project parameter is required", response.data["error"])

    def test_velocity_invalid_project_uuid(self):
        """Test velocity endpoint with invalid project UUID."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            "/api/v1/reporting/reports/velocity/?project=invalid-uuid"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("format", response.data["error"].lower())

    def test_velocity_nonexistent_project(self):
        """Test velocity endpoint with non-existent project."""
        self.client.force_authenticate(user=self.owner_user)
        fake_uuid = uuid.uuid4()

        response = self.client.get(
            f"/api/v1/reporting/reports/velocity/?project={fake_uuid}"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("not found", response.data["error"].lower())

    def test_velocity_no_permission(self):
        """Test velocity endpoint without permission."""
        self.client.force_authenticate(user=self.external_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/velocity/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("access", response.data["error"].lower())

    def test_velocity_invalid_num_sprints(self):
        """Test velocity endpoint with invalid num_sprints."""
        self.client.force_authenticate(user=self.owner_user)

        # Test non-integer
        response = self.client.get(
            f"/api/v1/reporting/reports/velocity/?project={self.project.id}&num_sprints=abc"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test out of range
        response = self.client.get(
            f"/api/v1/reporting/reports/velocity/?project={self.project.id}&num_sprints=100"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_velocity_success(self):
        """Test successful velocity endpoint call."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/velocity/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ================== SPRINT REPORT ENDPOINT TESTS ==================

    def test_sprint_report_missing_sprint_parameter(self):
        """Test sprint report without sprint parameter."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/reports/sprint-report/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sprint parameter is required", response.data["error"])

    def test_sprint_report_invalid_sprint_uuid(self):
        """Test sprint report with invalid sprint UUID."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            "/api/v1/reporting/reports/sprint-report/?sprint=invalid-uuid"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("format", response.data["error"].lower())

    def test_sprint_report_nonexistent_sprint(self):
        """Test sprint report with non-existent sprint."""
        self.client.force_authenticate(user=self.owner_user)
        fake_uuid = uuid.uuid4()

        response = self.client.get(
            f"/api/v1/reporting/reports/sprint-report/?sprint={fake_uuid}"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("not found", response.data["error"].lower())

    def test_sprint_report_no_permission(self):
        """Test sprint report without permission."""
        self.client.force_authenticate(user=self.external_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/sprint-report/?sprint={self.sprint.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("access", response.data["error"].lower())

    def test_sprint_report_success(self):
        """Test successful sprint report call."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/sprint-report/?sprint={self.sprint.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ================== TEAM METRICS ENDPOINT TESTS ==================

    def test_team_metrics_missing_project_parameter(self):
        """Test team metrics without project parameter."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/reports/team-metrics/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project parameter is required", response.data["error"])

    def test_team_metrics_invalid_period(self):
        """Test team metrics with invalid period."""
        self.client.force_authenticate(user=self.owner_user)

        # Test non-integer
        response = self.client.get(
            f"/api/v1/reporting/reports/team-metrics/?project={self.project.id}&period=abc"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test out of range
        response = self.client.get(
            f"/api/v1/reporting/reports/team-metrics/?project={self.project.id}&period=500"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_team_metrics_success(self):
        """Test successful team metrics call."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/team-metrics/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ================== CUMULATIVE FLOW ENDPOINT TESTS ==================

    def test_cumulative_flow_missing_project_parameter(self):
        """Test cumulative flow without project parameter."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/reports/cumulative-flow/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project parameter is required", response.data["error"])

    def test_cumulative_flow_invalid_days(self):
        """Test cumulative flow with invalid days."""
        self.client.force_authenticate(user=self.owner_user)

        # Test non-integer
        response = self.client.get(
            f"/api/v1/reporting/reports/cumulative-flow/?project={self.project.id}&days=abc"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test out of range
        response = self.client.get(
            f"/api/v1/reporting/reports/cumulative-flow/?project={self.project.id}&days=200"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cumulative_flow_success(self):
        """Test successful cumulative flow call."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/cumulative-flow/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ================== DASHBOARD ENDPOINT TESTS ==================

    def test_dashboard_missing_project_parameter(self):
        """Test dashboard without project parameter."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/reports/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project parameter is required", response.data["error"])

    def test_dashboard_success(self):
        """Test successful dashboard call."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/dashboard/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ================== LIST SNAPSHOTS ENDPOINT TESTS ==================

    def test_list_snapshots_missing_project_parameter(self):
        """Test list snapshots without project parameter."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/reports/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project parameter is required", response.data["error"])

    def test_list_snapshots_success(self):
        """Test successful list snapshots call."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            f"/api/v1/reporting/reports/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    # ================== WORKSPACE MEMBER ACCESS TESTS ==================

    def test_workspace_member_can_access_reports(self):
        """Test that workspace members can access project reports."""
        workspace_user = User.objects.create_user(
            email="workspace@test.com", username="workspace", password="testpass123"
        )
        WorkspaceMember.objects.create(
            workspace=self.workspace, user=workspace_user, role="member", is_active=True
        )

        self.client.force_authenticate(user=workspace_user)

        # Test velocity
        response = self.client.get(
            f"/api/v1/reporting/reports/velocity/?project={self.project.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test sprint report
        response = self.client.get(
            f"/api/v1/reporting/reports/sprint-report/?sprint={self.sprint.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DiagramEndpointTestCase(TestCase):
    """Test diagram endpoints with comprehensive validation."""

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
        self.owner_user = User.objects.create_user(
            email="owner@test.com", username="owner", password="testpass123"
        )
        self.external_user = User.objects.create_user(
            email="external@test.com", username="external", password="testpass123"
        )

        # Set up permissions
        ProjectTeamMember.objects.create(
            project=self.project, user=self.owner_user, role="owner", is_active=True
        )

    def test_list_diagrams_missing_project_parameter(self):
        """Test list diagrams without project parameter."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/diagrams/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project parameter is required", response.data["error"])

    def test_list_diagrams_invalid_project_uuid(self):
        """Test list diagrams with invalid project UUID."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get("/api/v1/reporting/diagrams/?project=invalid-uuid")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("format", response.data["error"].lower())

    def test_list_diagrams_no_permission(self):
        """Test list diagrams without permission."""
        self.client.force_authenticate(user=self.external_user)

        response = self.client.get(
            f"/api/v1/reporting/diagrams/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("access", response.data["error"].lower())

    def test_list_diagrams_success(self):
        """Test successful list diagrams call."""
        self.client.force_authenticate(user=self.owner_user)

        response = self.client.get(
            f"/api/v1/reporting/diagrams/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
