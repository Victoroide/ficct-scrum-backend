"""
Django admin for Notifications app.
"""

from django.contrib import admin
from django.utils import timezone

from apps.notifications.models import (
    Notification,
    NotificationPreference,
    ProjectNotificationSettings,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin for Notification."""

    list_display = [
        "recipient",
        "notification_type",
        "title",
        "is_read",
        "email_sent",
        "slack_sent",
        "created_at",
    ]
    list_filter = ["notification_type", "is_read", "email_sent", "slack_sent", "created_at"]
    search_fields = ["recipient__email", "title", "message"]
    readonly_fields = ["created_at", "read_at"]
    ordering = ["-created_at"]

    actions = ["mark_as_read", "mark_as_unread"]

    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read."""
        count = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f"{count} notifications marked as read.")

    mark_as_read.short_description = "Mark selected as read"

    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread."""
        count = queryset.update(is_read=False, read_at=None)
        self.message_user(request, f"{count} notifications marked as unread.")

    mark_as_unread.short_description = "Mark selected as unread"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin for NotificationPreference."""

    list_display = [
        "user",
        "email_enabled",
        "in_app_enabled",
        "slack_enabled",
        "digest_enabled",
    ]
    list_filter = [
        "email_enabled",
        "in_app_enabled",
        "slack_enabled",
        "digest_enabled",
    ]
    search_fields = ["user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ProjectNotificationSettings)
class ProjectNotificationSettingsAdmin(admin.ModelAdmin):
    """Admin for ProjectNotificationSettings."""

    list_display = ["project_id", "slack_enabled"]
    search_fields = ["slack_channel"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Project", {
            "fields": ("project_id",)
        }),
        ("Slack Integration", {
            "fields": ("slack_enabled", "slack_webhook_url", "slack_channel")
        }),
        ("Event Triggers", {
            "fields": ("notify_on_issue_create", "notify_on_issue_update", "notify_on_status_change", "notify_on_sprint_event", "notify_on_anomaly")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
