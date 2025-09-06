from django.db import models
from django.conf import settings
from .alert_rule_model import AlertRule
import uuid


class Alert(models.Model):
    STATUS_CHOICES = [
        ('triggered', 'Triggered'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('suppressed', 'Suppressed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        AlertRule,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='triggered')
    message = models.TextField()
    details = models.JSONField(default=dict)
    triggered_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'alerts'
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['status', 'triggered_at']),
            models.Index(fields=['rule', 'triggered_at']),
        ]

    def __str__(self):
        return f"{self.rule.name} - {self.status} - {self.triggered_at}"
