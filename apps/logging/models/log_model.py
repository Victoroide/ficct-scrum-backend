from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import uuid


class SystemLog(models.Model):
    LOG_LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    ACTION_TYPE_CHOICES = [
        ('authentication', 'Authentication'),
        ('authorization', 'Authorization'),
        ('crud_operation', 'CRUD Operation'),
        ('api_request', 'API Request'),
        ('system_event', 'System Event'),
        ('security_event', 'Security Event'),
        ('performance', 'Performance'),
        ('integration', 'Integration'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES)
    action = models.CharField(max_length=100)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES, default='system_event')
    message = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_logs'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.TextField(blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    execution_time = models.FloatField(null=True, blank=True)
    
    # Generic foreign key for related objects
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    metadata = models.JSONField(default=dict, blank=True)
    stack_trace = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'system_logs'
        verbose_name = 'System Log'
        verbose_name_plural = 'System Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['level', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        return f"{self.level} - {self.action} - {self.created_at}"


class ErrorLog(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    stack_trace = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='error_logs'
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
        related_name='resolved_errors'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'error_logs'
        verbose_name = 'Error Log'
        verbose_name_plural = 'Error Logs'
        ordering = ['-last_occurrence']
        indexes = [
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['error_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.error_type} - {self.severity} - {self.occurrence_count} times"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('permission_change', 'Permission Change'),
        ('status_change', 'Status Change'),
        ('export', 'Export'),
        ('import', 'Import'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Generic foreign key for the affected object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    session_id = models.CharField(max_length=255, blank=True)
    additional_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['resource_type', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.resource_type} - {self.created_at}"


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
