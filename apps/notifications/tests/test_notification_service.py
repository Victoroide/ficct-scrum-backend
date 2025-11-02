"""
Unit tests for notification service.

All external services are mocked - no real email or Slack calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from django.utils import timezone

from apps.notifications.services import NotificationService
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.tests.factories import (
    NotificationFactory,
    NotificationPreferenceFactory,
)
from apps.authentication.tests.factories import UserFactory
from apps.projects.tests.factories import IssueFactory, ProjectFactory


@pytest.mark.django_db
class TestNotificationService:
    """Test NotificationService methods."""

    def setup_method(self):
        """Set up test data."""
        self.service = NotificationService()
        self.user = UserFactory()
        self.project = ProjectFactory()

    def test_create_notification_success(self):
        """Test creating a notification."""
        notification = self.service.create_notification(
            recipient=self.user,
            notification_type="issue_assigned",
            title="Issue assigned to you",
            message="You have been assigned to TEST-123",
        )

        assert notification is not None
        assert notification.recipient == self.user
        assert notification.notification_type == "issue_assigned"
        assert notification.title == "Issue assigned to you"
        assert not notification.is_read

    def test_create_notification_respects_user_preferences(self):
        """Test notification respects user preferences."""
        # Disable issue_assigned notifications
        NotificationPreferenceFactory(
            user=self.user,
            in_app_enabled=False,
        )

        notification = self.service.create_notification(
            recipient=self.user,
            notification_type="issue_assigned",
            title="Test",
            message="Test",
        )

        # Should not create if in_app disabled
        assert notification is None or not notification.in_app_enabled

    @patch("apps.notifications.services.notification_service.EmailService")
    def test_create_notification_with_email(self, mock_email_service):
        """Test notification with email delivery."""
        mock_email = MagicMock()
        mock_email.send_notification_email.return_value = True
        mock_email_service.return_value = mock_email

        NotificationPreferenceFactory(
            user=self.user,
            email_enabled=True,
        )

        notification = self.service.create_notification(
            recipient=self.user,
            notification_type="issue_assigned",
            title="Test",
            message="Test message",
            send_email=True,
        )

        assert notification is not None
        # Email should be sent if preference enabled

    @patch("apps.notifications.services.notification_service.SlackService")
    def test_create_notification_with_slack(self, mock_slack_service):
        """Test notification with Slack delivery."""
        mock_slack = MagicMock()
        mock_slack.send_notification.return_value = True
        mock_slack_service.return_value = mock_slack

        NotificationPreferenceFactory(
            user=self.user,
            slack_enabled=True,
        )

        notification = self.service.create_notification(
            recipient=self.user,
            notification_type="issue_assigned",
            title="Test",
            message="Test message",
            send_slack=True,
        )

        assert notification is not None

    def test_mark_as_read(self):
        """Test marking notification as read."""
        notification = NotificationFactory(recipient=self.user, is_read=False)

        self.service.mark_as_read(notification.id, self.user)

        notification.refresh_from_db()
        assert notification.is_read
        assert notification.read_at is not None

    def test_mark_all_as_read(self):
        """Test marking all notifications as read."""
        NotificationFactory.create_batch(3, recipient=self.user, is_read=False)

        count = self.service.mark_all_as_read(self.user)

        assert count == 3
        assert Notification.objects.filter(recipient=self.user, is_read=False).count() == 0

    def test_get_unread_count(self):
        """Test getting unread notification count."""
        NotificationFactory.create_batch(5, recipient=self.user, is_read=False)
        NotificationFactory.create_batch(2, recipient=self.user, is_read=True)

        count = self.service.get_unread_count(self.user)

        assert count == 5

    def test_get_notifications_for_user(self):
        """Test retrieving user notifications."""
        NotificationFactory.create_batch(3, recipient=self.user)
        other_user = UserFactory()
        NotificationFactory.create_batch(2, recipient=other_user)

        notifications = self.service.get_notifications_for_user(self.user)

        assert notifications.count() == 3
        assert all(n.recipient == self.user for n in notifications)

    def test_delete_old_notifications(self):
        """Test deleting old read notifications."""
        # Create old read notification
        old_date = timezone.now() - timezone.timedelta(days=100)
        old_notification = NotificationFactory(
            recipient=self.user,
            is_read=True,
        )
        old_notification.created_at = old_date
        old_notification.save()

        # Create recent notification
        recent_notification = NotificationFactory(
            recipient=self.user,
            is_read=True,
        )

        count = self.service.delete_old_notifications(days=90)

        assert count >= 1
        assert not Notification.objects.filter(id=old_notification.id).exists()
        assert Notification.objects.filter(id=recent_notification.id).exists()


@pytest.mark.django_db
class TestNotificationPreferences:
    """Test notification preference handling."""

    def setup_method(self):
        """Set up test data."""
        self.service = NotificationService()
        self.user = UserFactory()

    def test_get_user_preferences(self):
        """Test retrieving user preferences."""
        prefs = NotificationPreferenceFactory(
            user=self.user,
            email_enabled=True,
            in_app_enabled=True,
        )

        retrieved_prefs = self.service.get_user_preferences(self.user)

        assert retrieved_prefs is not None
        assert retrieved_prefs.email_enabled
        assert retrieved_prefs.in_app_enabled

    def test_update_user_preferences(self):
        """Test updating user preferences."""
        NotificationPreferenceFactory(
            user=self.user,
            email_enabled=True,
        )

        updated = self.service.update_user_preferences(
            user=self.user,
            email_enabled=False,
            slack_enabled=True,
        )

        assert not updated.email_enabled
        assert updated.slack_enabled

    def test_create_default_preferences(self):
        """Test creating default preferences for new user."""
        prefs = self.service.get_or_create_preferences(self.user)

        assert prefs is not None
        assert prefs.user == self.user
        assert prefs.email_enabled  # Default should be True
        assert prefs.in_app_enabled  # Default should be True


@pytest.mark.django_db
class TestNotificationFiltering:
    """Test notification filtering logic."""

    def setup_method(self):
        """Set up test data."""
        self.service = NotificationService()
        self.user = UserFactory()

    def test_filter_by_type(self):
        """Test filtering notifications by type."""
        NotificationFactory.create_batch(
            2,
            recipient=self.user,
            notification_type="issue_assigned",
        )
        NotificationFactory.create_batch(
            3,
            recipient=self.user,
            notification_type="issue_commented",
        )

        assigned = self.service.get_notifications_by_type(
            self.user, "issue_assigned"
        )

        assert assigned.count() == 2

    def test_filter_by_read_status(self):
        """Test filtering by read status."""
        NotificationFactory.create_batch(
            4,
            recipient=self.user,
            is_read=False,
        )
        NotificationFactory.create_batch(
            2,
            recipient=self.user,
            is_read=True,
        )

        unread = self.service.get_unread_notifications(self.user)

        assert unread.count() == 4

    def test_pagination(self):
        """Test notification pagination."""
        NotificationFactory.create_batch(25, recipient=self.user)

        page1 = self.service.get_notifications_for_user(self.user, limit=10)

        assert page1.count() <= 10
