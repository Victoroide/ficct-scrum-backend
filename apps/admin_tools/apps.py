"""
Admin Tools app configuration.
"""

from django.apps import AppConfig


class AdminToolsConfig(AppConfig):
    """Configuration for admin tools app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.admin_tools"
    verbose_name = "Admin Tools"
