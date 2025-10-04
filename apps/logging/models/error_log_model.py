import uuid

from django.conf import settings
from django.db import models


class ErrorLog(models.Model):
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("investigating", "Investigating"),
        ("resolved", "Resolved"),
        ("ignored", "Ignored"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    stack_trace = models.TextField()
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="error_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    environment_info = models.JSONField(default=dict, blank=True)
    occurrence_count = models.PositiveIntegerField(default=1)
    first_occurrence = models.DateTimeField(auto_now_add=True)
    last_occurrence = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_errors",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "error_logs"
        verbose_name = "Error Log"
        verbose_name_plural = "Error Logs"
        ordering = ["-last_occurrence"]
        indexes = [
            models.Index(fields=["severity", "status"]),
            models.Index(fields=["error_type", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.error_type} - {self.severity} - {self.occurrence_count} times"
