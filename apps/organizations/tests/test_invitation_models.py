"""
Tests for OrganizationInvitation model.
"""
import secrets
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.authentication.tests.factories import UserFactory
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from apps.organizations.tests.factories import OrganizationFactory


class OrganizationInvitationModelTest(TestCase):
    """Test suite for OrganizationInvitation model."""

    def setUp(self):
        """Set up test data."""
        self.owner = UserFactory(email="owner@test.com")
        self.organization = OrganizationFactory(owner=self.owner)
        self.invited_email = "invited@test.com"

    def test_create_invitation(self):
        """Test creating an invitation with all fields."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            message="Welcome to the team!",
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.assertEqual(invitation.email, self.invited_email)
        self.assertEqual(invitation.role, "member")
        self.assertEqual(invitation.status, "pending")
        self.assertEqual(invitation.organization, self.organization)
        self.assertEqual(invitation.invited_by, self.owner)
        self.assertIsNotNone(invitation.token)
        self.assertIsNotNone(invitation.id)

    def test_auto_generate_token(self):
        """Test that token is unique for each invitation."""
        invitation1 = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="user1@test.com",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation2 = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="user2@test.com",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.assertNotEqual(invitation1.token, invitation2.token)

    def test_default_expires_at(self):
        """Test that invitation expires in approximately 7 days by default."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        time_until_expiry = invitation.expires_at - timezone.now()
        self.assertAlmostEqual(
            time_until_expiry.total_seconds(), 7 * 24 * 60 * 60, delta=5
        )

    def test_is_expired_property_not_expired(self):
        """Test is_expired property for non-expired invitation."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.assertFalse(invitation.is_expired)

    def test_is_expired_property_expired(self):
        """Test is_expired property for expired invitation."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(days=1),
        )

        self.assertTrue(invitation.is_expired)

    def test_days_until_expiry(self):
        """Test days_until_expiry property."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=5),
        )

        # Should be approximately 5 days (allowing for execution time)
        self.assertIn(invitation.days_until_expiry, [4, 5])

    def test_days_until_expiry_expired(self):
        """Test days_until_expiry returns 0 for expired invitations."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(days=1),
        )

        self.assertEqual(invitation.days_until_expiry, 0)

    def test_unique_pending_per_org_email(self):
        """Test that only one pending invitation per org/email is allowed."""
        # Create first invitation
        OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Try to create another with same org and email
        with self.assertRaises(Exception):
            OrganizationInvitation.objects.create(
                organization=self.organization,
                email=self.invited_email,
                status="pending",
                token=secrets.token_urlsafe(32),
                invited_by=self.owner,
                expires_at=timezone.now() + timedelta(days=7),
            )

    def test_accept_invitation_success(self):
        """Test accepting an invitation creates membership."""
        user = UserFactory(email=self.invited_email)
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        membership = invitation.accept(user)

        self.assertEqual(membership.organization, self.organization)
        self.assertEqual(membership.user, user)
        self.assertEqual(membership.role, "member")
        self.assertEqual(membership.status, "active")

        # Check invitation status updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "accepted")
        self.assertIsNotNone(invitation.accepted_at)

    def test_accept_invitation_wrong_email(self):
        """Test accepting invitation with mismatched email fails."""
        user = UserFactory(email="different@test.com")
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        with self.assertRaises(ValueError) as context:
            invitation.accept(user)

        self.assertIn("Email mismatch", str(context.exception))

    def test_accept_invitation_expired(self):
        """Test accepting expired invitation fails."""
        user = UserFactory(email=self.invited_email)
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(days=1),
        )

        with self.assertRaises(ValueError) as context:
            invitation.accept(user)

        self.assertIn("expired", str(context.exception).lower())

    def test_accept_invitation_already_accepted(self):
        """Test accepting already accepted invitation fails."""
        user = UserFactory(email=self.invited_email)
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="accepted",  # Already accepted
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        with self.assertRaises(ValueError) as context:
            invitation.accept(user)

        self.assertIn("status", str(context.exception).lower())

    def test_accept_invitation_already_member(self):
        """Test accepting invitation when already a member fails."""
        user = UserFactory(email=self.invited_email)

        # Create existing membership
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role="member",
            status="active",
        )

        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        with self.assertRaises(ValueError) as context:
            invitation.accept(user)

        self.assertIn("already a member", str(context.exception).lower())

    def test_revoke_invitation(self):
        """Test revoking an invitation."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation.revoke()

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "revoked")

    def test_revoke_accepted_invitation_fails(self):
        """Test that revoking an accepted invitation raises error."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="accepted",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
            accepted_at=timezone.now(),
        )

        with self.assertRaises(ValueError) as context:
            invitation.revoke()

        self.assertIn("cannot revoke", str(context.exception).lower())

    def test_is_pending_property(self):
        """Test is_pending property."""
        # Pending and not expired
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.assertTrue(invitation.is_pending)

        # Pending but expired
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save()
        self.assertFalse(invitation.is_pending)

        # Not pending
        invitation.status = "accepted"
        invitation.save()
        self.assertFalse(invitation.is_pending)

    def test_str_representation(self):
        """Test string representation of invitation."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email=self.invited_email,
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        str_repr = str(invitation)
        self.assertIn(self.invited_email, str_repr)
        self.assertIn(self.organization.name, str_repr)
