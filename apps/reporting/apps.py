from django.apps import AppConfig


class ReportingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reporting"
    verbose_name = "Reporting & Analytics"
    
    def ready(self):
        """Import signals when app is ready."""
        import apps.reporting.signals  # noqa
