import uuid

from django.conf import settings
from django.db import models

from .organization_membership_model import OrganizationMembership
from .organization_model import Organization


class OrganizationInvitation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20, choices=OrganizationMembership.ROLE_CHOICES, default="member"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    token = models.CharField(max_length=255, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_invitations_sent",
    )
    message = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization_invitations"
        verbose_name = "Organization Invitation"
        verbose_name_plural = "Organization Invitations"
        unique_together = ["organization", "email"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invitation to {self.email} for {self.organization.name}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() > self.expires_at

    @property
    def is_pending(self):
        return self.status == "pending" and not self.is_expired
