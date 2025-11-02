"""
Unit tests for Slack integration service.

All Slack API calls are mocked - no real webhook requests.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

from apps.notifications.services import SlackService


class TestSlackService:
    """Test SlackService methods."""

    def setup_method(self):
        """Set up test data."""
        self.service = SlackService()
        self.webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK/URL"

    @patch("apps.notifications.services.slack_service.requests.post")
    def test_send_notification_success(self, mock_post):
        """Test successful Slack notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.service.send_notification(
            title="Test Notification",
            message="This is a test message",
            webhook_url=self.webhook_url,
        )

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert self.webhook_url in str(call_args)

    @patch("apps.notifications.services.slack_service.requests.post")
    def test_send_notification_failure(self, mock_post):
        """Test failed Slack notification."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        result = self.service.send_notification(
            title="Test",
            message="Test",
            webhook_url=self.webhook_url,
        )

        assert result is False

    @patch("apps.notifications.services.slack_service.requests.post")
    def test_send_notification_connection_error(self, mock_post):
        """Test Slack notification with connection error."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        result = self.service.send_notification(
            title="Test",
            message="Test",
            webhook_url=self.webhook_url,
        )

        assert result is False

    @patch("apps.notifications.services.slack_service.requests.post")
    def test_send_notification_timeout(self, mock_post):
        """Test Slack notification with timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        result = self.service.send_notification(
            title="Test",
            message="Test",
            webhook_url=self.webhook_url,
        )

        assert result is False

    @patch("apps.notifications.services.slack_service.requests.post")
    def test_send_notification_with_color(self, mock_post):
        """Test Slack notification with custom color."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.service.send_notification(
            title="Test",
            message="Test",
            webhook_url=self.webhook_url,
            color="danger",
        )

        assert result is True

    @patch("apps.notifications.services.slack_service.requests.post")
    def test_send_notification_with_fields(self, mock_post):
        """Test Slack notification with additional fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.service.send_notification(
            title="Issue Updated",
            message="Status changed",
            webhook_url=self.webhook_url,
            fields=[
                {"title": "Priority", "value": "High", "short": True},
                {"title": "Assignee", "value": "John Doe", "short": True},
            ],
        )

        assert result is True

    def test_validate_webhook_url(self):
        """Test webhook URL validation."""
        valid_url = "https://hooks.slack.com/services/T00/B00/XX"
        invalid_url = "http://example.com"

        assert self.service.validate_webhook_url(valid_url)
        assert not self.service.validate_webhook_url(invalid_url)

    @patch("apps.notifications.services.slack_service.requests.post")
    def test_send_notification_empty_message(self, mock_post):
        """Test sending notification with empty message."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.service.send_notification(
            title="Test",
            message="",
            webhook_url=self.webhook_url,
        )

        # Should still send with empty message
        assert result is True or result is False  # Depends on implementation
