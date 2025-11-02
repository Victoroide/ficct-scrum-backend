"""Notifications app configuration."""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configuration for Notifications app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notifications"

    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.notifications.signals  # noqa
        except ImportError:
            pass
