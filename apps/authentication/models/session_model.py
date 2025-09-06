from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class UserSession(models.Model):
    SESSION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_key = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_info = models.JSONField(default=dict)
    location = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=SESSION_STATUS_CHOICES,
        default='active'
    )
    login_at = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    logout_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-login_at']

    def __str__(self):
        return f"{self.user.email} - {self.ip_address}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_active(self):
        return self.status == 'active' and not self.is_expired

    def revoke(self):
        self.status = 'revoked'
        self.logout_at = timezone.now()
        self.save()


