import pytest
from django.utils import timezone

from apps.reporting.models import ActivityLog, DiagramCache, ReportSnapshot, SavedFilter
from apps.reporting.tests.factories import (
    ActivityLogFactory,
    DiagramCacheFactory,
    ReportSnapshotFactory,
    SavedFilterFactory,
)


@pytest.mark.django_db
class TestSavedFilterModel:
    def test_create_saved_filter(self):
        saved_filter = SavedFilterFactory()

        assert saved_filter.id is not None
        assert saved_filter.user is not None
        assert saved_filter.project is not None

    def test_filter_count_property(self):
        saved_filter = SavedFilterFactory(
            filter_criteria={"status": "open", "priority": "P1", "assignee": "user123"}
        )
        assert saved_filter.filter_count == 3

    def test_formatted_criteria_property(self):
        saved_filter = SavedFilterFactory(
            filter_criteria={"status": "open", "priority": "P1"}
        )
        formatted = saved_filter.formatted_criteria
        assert "status=open" in formatted or "status" in formatted
        assert "priority" in formatted

    def test_unique_name_per_user_per_project(self):
        filter1 = SavedFilterFactory(name="My Filter")

        with pytest.raises(Exception):
            SavedFilterFactory(
                name="My Filter", user=filter1.user, project=filter1.project
            )

    def test_str_representation(self):
        saved_filter = SavedFilterFactory(name="Test Filter")
        assert "Test Filter" in str(saved_filter)
        assert saved_filter.user.email in str(saved_filter)


@pytest.mark.django_db
class TestActivityLogModel:
    def test_create_activity_log(self):
        activity = ActivityLogFactory()

        assert activity.id is not None
        assert activity.user is not None
        assert activity.action_type is not None

    def test_formatted_action_property(self):
        activity = ActivityLogFactory(
            action_type="created", object_repr="Issue PROJ-123"
        )
        formatted = activity.formatted_action
        assert "created" in formatted.lower()
        assert "PROJ-123" in formatted

    def test_time_ago_property(self):
        activity = ActivityLogFactory()
        time_ago = activity.time_ago
        assert time_ago is not None
        assert "ago" in time_ago or "just now" in time_ago

    def test_str_representation(self):
        activity = ActivityLogFactory(action_type="updated", object_repr="Test Object")
        str_repr = str(activity)
        assert "updated" in str_repr
        assert "Test Object" in str_repr


@pytest.mark.django_db
class TestDiagramCacheModel:
    def test_create_diagram_cache(self):
        cache = DiagramCacheFactory()

        assert cache.id is not None
        assert cache.project is not None
        assert cache.diagram_type is not None

    def test_is_expired_property(self):
        from datetime import timedelta

        future_cache = DiagramCacheFactory(
            expires_at=timezone.now() + timedelta(hours=1)
        )
        assert future_cache.is_expired is False

        past_cache = DiagramCacheFactory(expires_at=timezone.now() - timedelta(hours=1))
        assert past_cache.is_expired is True

    def test_increment_access_count(self):
        cache = DiagramCacheFactory(access_count=0)

        cache.increment_access_count()
        cache.refresh_from_db()

        assert cache.access_count == 1

        cache.increment_access_count()
        cache.refresh_from_db()

        assert cache.access_count == 2

    def test_str_representation(self):
        cache = DiagramCacheFactory(diagram_type="workflow")
        str_repr = str(cache)
        assert "Workflow" in str_repr or "workflow" in str_repr


@pytest.mark.django_db
class TestReportSnapshotModel:
    def test_create_report_snapshot(self):
        snapshot = ReportSnapshotFactory()

        assert snapshot.id is not None
        assert snapshot.project is not None
        assert snapshot.report_type is not None

    def test_formatted_period_property(self):
        from datetime import date

        snapshot = ReportSnapshotFactory(
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)
        )
        formatted = snapshot.formatted_period
        assert "2024-01-01" in formatted
        assert "2024-01-31" in formatted

    def test_download_url_property(self):
        snapshot = ReportSnapshotFactory()
        url = snapshot.download_url
        assert url is None

    def test_str_representation(self):
        snapshot = ReportSnapshotFactory(report_type="velocity")
        str_repr = str(snapshot)
        assert "Velocity" in str_repr or "velocity" in str_repr
