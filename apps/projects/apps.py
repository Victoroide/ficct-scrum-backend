from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projects"

    def ready(self):
        """
        Import signals when Django starts.
        This ensures that signal handlers are registered and will fire automatically.
        """
        import apps.projects.signals  # noqa: F401
