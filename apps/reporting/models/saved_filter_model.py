import uuid

from django.conf import settings
from django.db import models


class SavedFilter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_filters",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="saved_filters"
    )
    filter_criteria = models.JSONField(default=dict)
    is_public = models.BooleanField(default=False)
    shared_with_team = models.BooleanField(default=False)
    use_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "saved_filters"
        verbose_name = "Saved Filter"
        verbose_name_plural = "Saved Filters"
        unique_together = ["user", "project", "name"]
        ordering = ["-last_used_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "project"]),
            models.Index(fields=["is_public"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    @property
    def filter_count(self):
        return len(self.filter_criteria) if self.filter_criteria else 0

    @property
    def formatted_criteria(self):
        if not self.filter_criteria:
            return "No filters"
        return ", ".join([f"{k}={v}" for k, v in self.filter_criteria.items()])
