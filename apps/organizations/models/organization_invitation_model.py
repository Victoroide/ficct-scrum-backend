import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .organization_membership_model import OrganizationMembership
from .organization_model import Organization


class OrganizationInvitation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
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
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Invitation to {self.email} for {self.organization.name}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_pending(self):
        return self.status == "pending" and not self.is_expired

    @property
    def days_until_expiry(self):
        """Returns the number of days until invitation expires."""
        if self.is_expired:
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def send_invitation_email(self):
        """Send invitation email to the invitee."""
        from base.services import EmailService

        try:
            return EmailService.send_organization_invitation_email(
                invitation=self,
                invited_by_name=self.invited_by.full_name,
                organization_name=self.organization.name,
            )
        except Exception as e:
            from apps.logging.services import LoggerService

            LoggerService.log_error(
                action="invitation_email_send_failed",
                user=self.invited_by,
                error=str(e),
                details={"invitation_id": str(self.id), "email": self.email},
            )
            return False

    def accept(self, user):
        """
        Accept the invitation and create organization membership.

        Args:
            user: The user accepting the invitation

        Returns:
            OrganizationMembership: The created membership

        Raises:
            ValueError: If invitation is not valid for acceptance
        """
        if self.status != "pending":
            raise ValueError(f"Cannot accept invitation with status '{self.status}'")

        if self.is_expired:
            raise ValueError("Cannot accept expired invitation")

        if user.email != self.email:
            raise ValueError("Email mismatch: user email doesn't match invitation")

        # Check if user is already a member
        if OrganizationMembership.objects.filter(
            organization=self.organization, user=user, is_active=True
        ).exists():
            raise ValueError("User is already a member of this organization")

        # Create membership
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=self.role,
            status="active",
            invited_by=self.invited_by,
            joined_at=timezone.now(),
            invitation=self,
        )

        # Update invitation status
        self.status = "accepted"
        self.accepted_at = timezone.now()
        self.save(update_fields=["status", "accepted_at", "updated_at"])

        return membership

    def revoke(self):
        """Revoke the invitation (cancel it)."""
        if self.status == "accepted":
            raise ValueError("Cannot revoke an already accepted invitation")

        self.status = "revoked"
        self.save(update_fields=["status", "updated_at"])
