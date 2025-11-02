"""Machine Learning app configuration."""

from django.apps import AppConfig


class MlConfig(AppConfig):
    """Configuration for Machine Learning app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ml"
    verbose_name = "Machine Learning"

    def ready(self):
        """Import signals when app is ready."""
        pass  # Import signals here if needed
