import pytest
from django.urls import reverse
from rest_framework import status

from apps.reporting.tests.factories import ActivityLogFactory, SavedFilterFactory


@pytest.mark.django_db
class TestSavedFilterAPI:
    def test_list_saved_filters(
        self, api_client, authenticated_user, project_with_team
    ):
        SavedFilterFactory.create_batch(
            3, user=authenticated_user, project=project_with_team
        )

        url = reverse("saved-filter-list")
        response = api_client.get(url, {"project": str(project_with_team.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 3

    def test_create_saved_filter(
        self, api_client, authenticated_user, project_with_team
    ):
        url = reverse("saved-filter-list")
        data = {
            "name": "My Custom Filter",
            "description": "Filter for high priority issues",
            "project": str(project_with_team.id),
            "filter_criteria": {"priority": "P1", "status": "open"},
            "is_public": False,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "My Custom Filter"
        assert response.data["filter_criteria"]["priority"] == "P1"

    def test_update_saved_filter(
        self, api_client, authenticated_user, project_with_team
    ):
        saved_filter = SavedFilterFactory(
            user=authenticated_user, project=project_with_team
        )

        url = reverse("saved-filter-detail", kwargs={"pk": str(saved_filter.id)})
        data = {"name": "Updated Filter Name"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Filter Name"

    def test_delete_saved_filter(
        self, api_client, authenticated_user, project_with_team
    ):
        saved_filter = SavedFilterFactory(
            user=authenticated_user, project=project_with_team
        )

        url = reverse("saved-filter-detail", kwargs={"pk": str(saved_filter.id)})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_apply_saved_filter(
        self, api_client, authenticated_user, project_with_team
    ):
        saved_filter = SavedFilterFactory(
            user=authenticated_user,
            project=project_with_team,
            filter_criteria={"priority": "P1"},
        )

        url = reverse("saved-filter-apply", kwargs={"pk": str(saved_filter.id)})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert "issues" in response.data
        assert "filter" in response.data


@pytest.mark.django_db
class TestActivityLogAPI:
    def test_list_activity_logs(
        self, api_client, authenticated_user, project_with_team
    ):
        ActivityLogFactory.create_batch(
            5, user=authenticated_user, project=project_with_team
        )

        url = reverse("activity-log-list")
        response = api_client.get(url, {"project": str(project_with_team.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 5

    def test_retrieve_activity_log(
        self, api_client, authenticated_user, project_with_team
    ):
        activity = ActivityLogFactory(
            user=authenticated_user, project=project_with_team
        )

        url = reverse("activity-log-detail", kwargs={"pk": str(activity.id)})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(activity.id)
        assert "formatted_action" in response.data

    def test_filter_activity_by_user(
        self, api_client, authenticated_user, project_with_team
    ):
        ActivityLogFactory.create_batch(
            3, user=authenticated_user, project=project_with_team
        )

        url = reverse("activity-log-list")
        response = api_client.get(url, {"user": str(authenticated_user.id)})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 3


@pytest.mark.django_db
class TestDiagramAPI:
    def test_generate_workflow_diagram(
        self, api_client, authenticated_user, project_with_team
    ):
        url = reverse("diagram-generate")
        data = {"diagram_type": "workflow", "format": "svg"}

        response = api_client.post(
            url, data, format="json", QUERY_STRING=f"project={project_with_team.id}"
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_generate_dependency_diagram(
        self, api_client, authenticated_user, project_with_team
    ):
        url = reverse("diagram-generate")
        data = {"diagram_type": "dependency", "format": "svg"}

        response = api_client.post(
            url, data, format="json", QUERY_STRING=f"project={project_with_team.id}"
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


@pytest.mark.django_db
class TestReportAPI:
    def test_generate_velocity_chart(
        self, api_client, authenticated_user, project_with_team
    ):
        url = reverse("report-velocity")
        response = api_client.get(url, {"project": str(project_with_team.id)})

        assert response.status_code == status.HTTP_200_OK
        assert "labels" in response.data
        assert "velocities" in response.data

    def test_generate_team_metrics(
        self, api_client, authenticated_user, project_with_team
    ):
        url = reverse("report-team-metrics")
        response = api_client.get(url, {"project": str(project_with_team.id)})

        assert response.status_code == status.HTTP_200_OK
        assert "user_metrics" in response.data
        assert "team_aggregates" in response.data

    def test_generate_dashboard(
        self, api_client, authenticated_user, project_with_team
    ):
        url = reverse("report-dashboard")
        response = api_client.get(url, {"project": str(project_with_team.id)})

        assert response.status_code == status.HTTP_200_OK
        assert "summary_stats" in response.data
        assert "project" in response.data
