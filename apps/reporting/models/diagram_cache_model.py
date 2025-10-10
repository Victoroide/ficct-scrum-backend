import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class DiagramCache(models.Model):
    DIAGRAM_TYPE_CHOICES = [
        ("workflow", "Workflow Diagram"),
        ("dependency", "Dependency Diagram"),
        ("roadmap", "Roadmap"),
        ("uml", "UML Diagram"),
        ("architecture", "Architecture Diagram"),
    ]

    FORMAT_CHOICES = [
        ("svg", "SVG"),
        ("png", "PNG"),
        ("json", "JSON"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="diagram_caches"
    )
    diagram_type = models.CharField(max_length=20, choices=DIAGRAM_TYPE_CHOICES)
    diagram_data = models.TextField()
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="svg")
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="generated_diagrams",
    )
    parameters = models.JSONField(default=dict, blank=True)
    cache_key = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    generated_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(auto_now=True)
    access_count = models.IntegerField(default=0)

    class Meta:
        db_table = "diagram_caches"
        verbose_name = "Diagram Cache"
        verbose_name_plural = "Diagram Caches"
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["project", "diagram_type"]),
            models.Index(fields=["cache_key"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.project.key} - {self.get_diagram_type_display()}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def increment_access_count(self):
        self.access_count += 1
        self.save(update_fields=["access_count", "last_accessed_at"])
