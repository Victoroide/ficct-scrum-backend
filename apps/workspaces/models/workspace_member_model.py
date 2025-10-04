import uuid

from django.conf import settings
from django.db import models


class WorkspaceMember(models.Model):
    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("manager", "Manager"),
        ("member", "Member"),
        ("viewer", "Viewer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    permissions = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workspace_members"
        verbose_name = "Workspace Member"
        verbose_name_plural = "Workspace Members"
        unique_together = ["workspace", "user"]
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.full_name} - {self.workspace.name} ({self.role})"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def can_manage_projects(self):
        return self.role in ["admin", "manager"]

    @property
    def can_edit_workspace(self):
        return self.role in ["admin", "manager"]
