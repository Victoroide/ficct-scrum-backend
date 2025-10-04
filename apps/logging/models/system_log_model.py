import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class SystemLog(models.Model):
    LOG_LEVEL_CHOICES = [
        ("DEBUG", "Debug"),
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    ACTION_TYPE_CHOICES = [
        ("authentication", "Authentication"),
        ("authorization", "Authorization"),
        ("crud_operation", "CRUD Operation"),
        ("api_request", "API Request"),
        ("system_event", "System Event"),
        ("security_event", "Security Event"),
        ("performance", "Performance"),
        ("integration", "Integration"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES)
    action = models.CharField(max_length=100)
    action_type = models.CharField(
        max_length=20, choices=ACTION_TYPE_CHOICES, default="system_event"
    )
    message = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.TextField(blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    execution_time = models.FloatField(null=True, blank=True)

    # Generic foreign key for related objects
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.CharField(max_length=255, null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    metadata = models.JSONField(default=dict, blank=True)
    stack_trace = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "system_logs"
        verbose_name = "System Log"
        verbose_name_plural = "System Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["level", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]

    def __str__(self):
        return f"{self.level} - {self.action} - {self.created_at}"
