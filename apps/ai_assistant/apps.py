"""AI Assistant app configuration."""

from django.apps import AppConfig


class AiAssistantConfig(AppConfig):
    """Configuration for AI Assistant app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_assistant"
    verbose_name = "AI Assistant"

    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.ai_assistant.signals  # noqa
        except ImportError:
            pass
