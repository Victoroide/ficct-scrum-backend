"""Notification models for user alerts and preferences."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class NotificationPreference(models.Model):
    """User notification preferences."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preferences"
    )

    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    slack_enabled = models.BooleanField(default=False)

    # Notification type preferences
    notification_types = models.JSONField(
        default=dict,
        help_text="Dictionary of notification types and their enabled status",
    )
    # Example: {"issue_assigned": True, "issue_commented": True, "sprint_started": False}  # noqa: E501

    # Frequency settings
    digest_enabled = models.BooleanField(
        default=False, help_text="Receive daily digest instead of real-time"
    )
    digest_time = models.TimeField(
        null=True, blank=True, help_text="Time to send daily digest"
    )

    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preferences"

    def __str__(self):
        return f"Preferences for {self.user.email}"

    def is_type_enabled(self, notification_type: str) -> bool:
        """Check if specific notification type is enabled."""
        return self.notification_types.get(notification_type, True)


class Notification(models.Model):
    """User notifications."""

    NOTIFICATION_TYPES = [
        ("issue_assigned", "Issue Assigned"),
        ("issue_updated", "Issue Updated"),
        ("issue_commented", "Issue Commented"),
        ("status_changed", "Status Changed"),
        ("sprint_started", "Sprint Started"),
        ("sprint_completed", "Sprint Completed"),
        ("deadline_approaching", "Deadline Approaching"),
        ("mention", "Mentioned"),
        ("ai_insight", "AI Insight"),
        ("anomaly_detected", "Anomaly Detected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )

    # Notification details
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.URLField(blank=True, help_text="Link to related resource")

    # Additional data (issue_id, project_id, etc.)
    data = models.JSONField(default=dict, blank=True)

    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Delivery tracking
    email_sent = models.BooleanField(default=False)
    slack_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient.email}"

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            from django.utils import timezone

            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class ProjectNotificationSettings(models.Model):
    """Project-level notification settings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_id = models.UUIDField(unique=True)

    # Slack integration
    slack_webhook_url = models.URLField(blank=True)
    slack_channel = models.CharField(max_length=100, blank=True)
    slack_enabled = models.BooleanField(default=False)

    # Event triggers
    notify_on_issue_create = models.BooleanField(default=True)
    notify_on_issue_update = models.BooleanField(default=False)
    notify_on_status_change = models.BooleanField(default=True)
    notify_on_sprint_event = models.BooleanField(default=True)
    notify_on_anomaly = models.BooleanField(default=True)

    # Custom settings
    custom_settings = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_notification_settings"

    def __str__(self):
        return f"Settings for project {self.project_id}"
