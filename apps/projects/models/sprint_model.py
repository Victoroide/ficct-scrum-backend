import uuid
from datetime import date

from django.conf import settings
from django.db import models


class Sprint(models.Model):
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="sprints"
    )
    name = models.CharField(max_length=255)
    goal = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    completed_points = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    committed_points = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_sprints",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sprints"
        verbose_name = "Sprint"
        verbose_name_plural = "Sprints"
        unique_together = ["project", "name"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.project.key} - {self.name}"

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0

    @property
    def remaining_days(self):
        if self.status == "active" and self.end_date:
            remaining = (self.end_date - date.today()).days
            return max(0, remaining)
        return 0

    @property
    def progress_percentage(self):
        if self.committed_points and self.committed_points > 0:
            return round((self.completed_points / self.committed_points) * 100, 2)
        return 0

    @property
    def issue_count(self):
        return self.issues.filter(is_active=True).count()

    @property
    def completed_issue_count(self):
        return self.issues.filter(is_active=True, status__is_final=True).count()
