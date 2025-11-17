import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):
    ACTION_TYPE_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("deleted", "Deleted"),
        ("transitioned", "Transitioned"),
        ("commented", "Commented"),
        ("attached", "Attached"),
        ("linked", "Linked"),
        ("assigned", "Assigned"),
        ("sprint_added", "Added to Sprint"),
        ("sprint_removed", "Removed from Sprint"),
        ("archived", "Archived"),
        ("restored", "Restored"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.CharField(max_length=255, null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(max_length=500)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_logs"
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.user.email} {self.action_type} {self.object_repr}"

    @property
    def formatted_action(self):
        user_name = self.user.get_full_name() or self.user.email
        action = self.get_action_type_display()
        return f"{user_name} {action} {self.object_repr}"

    @property
    def time_ago(self):
        now = timezone.now()
        diff = now - self.created_at

        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            plural = "s" if minutes > 1 else ""
            return f"{minutes} minute{plural} ago"
        else:
            return "just now"
