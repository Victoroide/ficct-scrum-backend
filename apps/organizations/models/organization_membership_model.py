import uuid

from django.conf import settings
from django.db import models

from .organization_model import Organization


class OrganizationMembership(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Administrator"),
        ("manager", "Manager"),
        ("member", "Member"),
        ("guest", "Guest"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("suspended", "Suspended"),
        ("inactive", "Inactive"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    permissions = models.JSONField(default=dict)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    invitation = models.ForeignKey(
        "OrganizationInvitation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships",
        help_text="The invitation that originated this membership",
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization_memberships"
        verbose_name = "Organization Membership"
        verbose_name_plural = "Organization Memberships"
        unique_together = ["organization", "user"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.full_name} - {self.organization.name} ({self.role})"

    @property
    def is_owner(self):
        return self.role == "owner"

    @property
    def is_admin(self):
        return self.role in ["owner", "admin"]

    @property
    def can_manage_members(self):
        return self.role in ["owner", "admin", "manager"]
