from django.db import models
from django.conf import settings
import uuid


class AlertRule(models.Model):
    CONDITION_CHOICES = [
        ('error_count', 'Error Count'),
        ('error_rate', 'Error Rate'),
        ('response_time', 'Response Time'),
        ('user_activity', 'User Activity'),
        ('security_event', 'Security Event'),
        ('system_resource', 'System Resource'),
    ]

    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('paused', 'Paused'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    condition_type = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    condition_config = models.JSONField(default=dict)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    notification_channels = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_alert_rules'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'alert_rules'
        verbose_name = 'Alert Rule'
        verbose_name_plural = 'Alert Rules'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.severity}"
