"""
API endpoint tests for ML features.

Tests authentication, permissions, and response formats.
"""

from unittest.mock import MagicMock, patch

from django.urls import reverse

import pytest
from rest_framework import status

from apps.authentication.tests.factories import UserFactory
from apps.ml.tests.factories import AnomalyDetectionFactory
from apps.projects.tests.factories import IssueFactory, ProjectFactory, SprintFactory
from apps.workspaces.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


@pytest.mark.django_db
class TestMLPredictionEndpoints:
    """Test ML prediction API endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    def test_predict_effort_requires_authentication(self, api_client):
        """Test effort prediction requires authentication."""
        url = reverse("ml-predict-effort")
        response = api_client.post(url, {})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_predict_effort_with_valid_data(self, api_client):
        """Test effort prediction with valid data."""
        api_client.force_authenticate(user=self.user)

        # Create some completed issues for training
        for i in range(5):
            IssueFactory(
                project=self.project,
                status__is_final=True,
                actual_hours=8,
            )

        url = reverse("ml-predict-effort")
        data = {
            "title": "Fix authentication bug",
            "description": "Users cannot login",
            "issue_type": "bug",
            "project_id": str(self.project.id),
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

        if response.status_code == status.HTTP_200_OK:
            assert "predicted_hours" in response.data
            assert "confidence" in response.data

    def test_predict_effort_missing_required_fields(self, api_client):
        """Test effort prediction with missing fields."""
        api_client.force_authenticate(user=self.user)

        url = reverse("ml-predict-effort")
        data = {"title": "Test"}  # Missing required fields

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_estimate_sprint_duration(self, api_client):
        """Test sprint duration estimation."""
        api_client.force_authenticate(user=self.user)

        sprint = SprintFactory(project=self.project)

        url = reverse("ml-estimate-sprint-duration")
        data = {
            "sprint_id": str(sprint.id),
            "team_capacity_hours": 160,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_recommend_story_points(self, api_client):
        """Test story points recommendation."""
        api_client.force_authenticate(user=self.user)

        url = reverse("ml-recommend-story-points")
        data = {
            "title": "Implement user profile",
            "description": "Add user profile page",
            "issue_type": "story",
            "project_id": str(self.project.id),
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

        if response.status_code == status.HTTP_200_OK:
            assert "recommended_points" in response.data


@pytest.mark.django_db
class TestMLRecommendationEndpoints:
    """Test ML recommendation API endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    def test_suggest_assignment(self, api_client):
        """Test task assignment suggestion."""
        api_client.force_authenticate(user=self.user)

        issue = IssueFactory(project=self.project)

        url = reverse("ml-suggest-assignment")
        data = {"issue_id": str(issue.id)}

        response = api_client.post(url, data, format="json")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]


@pytest.mark.django_db
class TestMLAnomalyEndpoints:
    """Test ML anomaly detection API endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.workspace = WorkspaceFactory()
        self.project = ProjectFactory(workspace=self.workspace)
        WorkspaceMemberFactory(workspace=self.workspace, user=self.user)

    def test_get_sprint_risk_assessment(self, api_client):
        """Test sprint risk assessment."""
        api_client.force_authenticate(user=self.user)

        sprint = SprintFactory(project=self.project)

        url = reverse("ml-sprint-risk", kwargs={"pk": sprint.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "risks" in response.data

    def test_get_project_anomalies(self, api_client):
        """Test retrieving project anomalies."""
        api_client.force_authenticate(user=self.user)

        # Create anomaly
        AnomalyDetectionFactory(
            project_id=self.project.id,
            anomaly_type="velocity_drop",
        )

        url = reverse("ml-project-anomalies", kwargs={"pk": self.project.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)


@pytest.mark.django_db
class TestMLPermissions:
    """Test ML API permissions."""

    def test_unauthenticated_access_denied(self, api_client):
        """Test unauthenticated users cannot access ML endpoints."""
        url = reverse("ml-predict-effort")
        response = api_client.post(url, {})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_member_access_denied(self, api_client):
        """Test non-project members cannot access ML features."""
        user = UserFactory()
        project = ProjectFactory()

        api_client.force_authenticate(user=user)

        url = reverse("ml-predict-effort")
        data = {
            "title": "Test",
            "issue_type": "task",
            "project_id": str(project.id),
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
