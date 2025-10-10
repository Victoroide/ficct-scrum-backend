"""
API tests for organization invitation system.
Tests the complete invitation workflow including email-based invitations.
"""
import secrets
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.authentication.tests.factories import UserFactory
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from apps.organizations.tests.factories import OrganizationFactory


class OrganizationInvitationAPITest(TestCase):
    """Test suite for organization invitation API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create owner user and organization
        self.owner = UserFactory(email="owner@test.com")
        self.organization = OrganizationFactory(owner=self.owner)

        # Create owner membership
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
            status="active",
            joined_at=timezone.now(),
        )

        # Create admin user
        self.admin = UserFactory(email="admin@test.com")
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.admin,
            role="admin",
            status="active",
            joined_at=timezone.now(),
        )

        # Create regular member
        self.member = UserFactory(email="member@test.com")
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role="member",
            status="active",
            joined_at=timezone.now(),
        )

    @patch("apps.organizations.models.organization_invitation_model.EmailService")
    def test_invite_existing_user_by_email(self, mock_email_service):
        """Test inviting an existing user creates membership directly."""
        # Create existing user
        existing_user = UserFactory(email="existing@test.com")

        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/v1/orgs/invitations/",
            {
                "organization": str(self.organization.id),
                "email": "existing@test.com",
                "role": "member",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "accepted")
        self.assertTrue(response.data["user_existed"])
        self.assertEqual(response.data["message"], "Usuario agregado a la organización")

        # Verify membership was created
        membership = OrganizationMembership.objects.filter(
            organization=self.organization, user=existing_user
        ).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, "member")
        self.assertEqual(membership.status, "active")

        # Verify NO invitation was created
        invitation = OrganizationInvitation.objects.filter(
            email="existing@test.com"
        ).first()
        self.assertIsNone(invitation)

    @patch("apps.organizations.models.organization_invitation_model.EmailService")
    def test_invite_new_user_by_email(self, mock_email_service):
        """Test inviting a non-existent user creates invitation."""
        mock_email_service.send_organization_invitation_email.return_value = True

        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/v1/orgs/invitations/",
            {
                "organization": str(self.organization.id),
                "email": "newuser@test.com",
                "role": "member",
                "message": "Join our team!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertFalse(response.data["user_existed"])
        self.assertTrue(response.data["invitation_sent"])
        self.assertIn("acceptance_url", response.data)

        # Verify invitation was created
        invitation = OrganizationInvitation.objects.filter(
            email="newuser@test.com"
        ).first()
        self.assertIsNotNone(invitation)
        self.assertEqual(invitation.role, "member")
        self.assertEqual(invitation.status, "pending")
        self.assertIsNotNone(invitation.token)

        # Verify email was sent
        mock_email_service.send_organization_invitation_email.assert_called_once()

    def test_cannot_invite_existing_member(self):
        """Test that inviting an existing member returns error."""
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/v1/orgs/invitations/",
            {
                "organization": str(self.organization.id),
                "email": self.member.email,  # Already a member
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already a member", str(response.data).lower())

    @patch("apps.organizations.models.organization_invitation_model.EmailService")
    def test_cannot_invite_with_pending_invitation(self, mock_email_service):
        """Test that creating duplicate pending invitation fails."""
        mock_email_service.send_organization_invitation_email.return_value = True

        # Create first invitation
        self.client.force_authenticate(user=self.owner)
        self.client.post(
            "/api/v1/orgs/invitations/",
            {
                "organization": str(self.organization.id),
                "email": "pending@test.com",
                "role": "member",
            },
            format="json",
        )

        # Try to create second invitation
        response = self.client.post(
            "/api/v1/orgs/invitations/",
            {
                "organization": str(self.organization.id),
                "email": "pending@test.com",
                "role": "member",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", str(response.data).lower())

    def test_only_admin_can_invite(self):
        """Test that only owner/admin/manager can invite."""
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            "/api/v1/orgs/invitations/",
            {
                "organization": str(self.organization.id),
                "email": "test@test.com",
                "role": "member",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("permission", str(response.data).lower())

    def test_verify_invitation_valid(self):
        """Test verifying a valid invitation token."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="verify@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # No authentication needed for verify endpoint
        response = self.client.get(
            f"/api/v1/orgs/invitations/verify/?token={invitation.token}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["email"], "verify@test.com")
        self.assertEqual(response.data["role"], "member")
        self.assertIn("organization", response.data)
        self.assertIn("invited_by", response.data)
        self.assertIn("days_remaining", response.data)

    def test_verify_invitation_expired(self):
        """Test verifying an expired invitation."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="expired@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
        )

        response = self.client.get(
            f"/api/v1/orgs/invitations/verify/?token={invitation.token}"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["valid"])
        self.assertIn("expirada", response.data["error"].lower())

    def test_verify_invitation_invalid_token(self):
        """Test verifying with invalid token."""
        response = self.client.get(
            "/api/v1/orgs/invitations/verify/?token=invalid-token-123"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["valid"])

    @patch("apps.organizations.serializers.invitation_serializer.EmailService")
    def test_accept_invitation_success(self, mock_email_service):
        """Test accepting an invitation successfully."""
        mock_email_service.send_organization_welcome_email.return_value = True

        # Create user with matching email
        user = UserFactory(email="accept@test.com")

        # Create invitation
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="accept@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/v1/orgs/invitations/accept/",
            {"token": invitation.token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("organization", response.data)
        self.assertIn("redirect_url", response.data)

        # Verify membership created
        membership = OrganizationMembership.objects.filter(
            organization=self.organization, user=user
        ).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.status, "active")

        # Verify invitation updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "accepted")
        self.assertIsNotNone(invitation.accepted_at)

    def test_accept_invitation_wrong_email(self):
        """Test accepting invitation with mismatched email fails."""
        user = UserFactory(email="different@test.com")

        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="invited@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/v1/orgs/invitations/accept/",
            {"token": invitation.token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no coincide", str(response.data).lower())

    def test_accept_invitation_expired(self):
        """Test accepting expired invitation fails."""
        user = UserFactory(email="expired@test.com")

        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="expired@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(days=1),
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/v1/orgs/invitations/accept/",
            {"token": invitation.token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expirado", str(response.data).lower())

    def test_accept_invitation_unauthenticated(self):
        """Test that unauthenticated users cannot accept invitations."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="test@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.post(
            "/api/v1/orgs/invitations/accept/",
            {"token": invitation.token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_pending_invitations(self):
        """Test listing pending invitations for an organization."""
        # Create invitations
        OrganizationInvitation.objects.create(
            organization=self.organization,
            email="pending1@test.com",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        OrganizationInvitation.objects.create(
            organization=self.organization,
            email="pending2@test.com",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        OrganizationInvitation.objects.create(
            organization=self.organization,
            email="accepted@test.com",
            status="accepted",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            f"/api/v1/orgs/invitations/?organization={self.organization.id}&status=pending"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_revoke_invitation(self):
        """Test revoking an invitation."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="revoke@test.com",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(f"/api/v1/orgs/invitations/{invitation.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify invitation was revoked (not deleted)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "revoked")

    def test_inviter_can_revoke_own_invitation(self):
        """Test that the inviter can revoke their own invitation."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="test@test.com",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.admin,  # Invited by admin
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(f"/api/v1/orgs/invitations/{invitation.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_member_cannot_revoke_invitation(self):
        """Test that regular members cannot revoke invitations."""
        invitation = OrganizationInvitation.objects.create(
            organization=self.organization,
            email="test@test.com",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=self.member)

        response = self.client.delete(f"/api/v1/orgs/invitations/{invitation.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class RegistrationWithInvitationTest(TestCase):
    """Test auto-acceptance of invitations during registration."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.owner = UserFactory(email="owner@test.com")
        self.organization = OrganizationFactory(owner=self.owner)

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
            status="active",
            joined_at=timezone.now(),
        )

    @patch("apps.authentication.viewsets.auth_viewset.EmailService")
    def test_register_auto_accepts_invitations(self, mock_email_service):
        """Test that registration auto-accepts pending invitations."""
        mock_email_service.send_welcome_email.return_value = True
        mock_email_service.send_organization_welcome_email.return_value = True

        # Create pending invitations
        OrganizationInvitation.objects.create(
            organization=self.organization,
            email="newuser@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Register new user
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "newuser@test.com",
                "username": "newuser",
                "first_name": "New",
                "last_name": "User",
                "password": "TestPassword123!",
                "password_confirm": "TestPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("auto_joined_organizations", response.data)
        self.assertEqual(response.data["pending_invitations_accepted"], 1)
        self.assertIn("redirect_suggestion", response.data)

        # Verify user was created and invitation accepted
        user = User.objects.get(email="newuser@test.com")
        membership = OrganizationMembership.objects.filter(
            organization=self.organization, user=user
        ).first()
        self.assertIsNotNone(membership)

        invitation = OrganizationInvitation.objects.get(email="newuser@test.com")
        self.assertEqual(invitation.status, "accepted")

    @patch("apps.authentication.viewsets.auth_viewset.EmailService")
    def test_register_accepts_multiple_invitations(self, mock_email_service):
        """Test that registration accepts multiple pending invitations."""
        mock_email_service.send_welcome_email.return_value = True
        mock_email_service.send_organization_welcome_email.return_value = True

        # Create second organization
        org2 = OrganizationFactory(owner=self.owner)

        # Create invitations from both organizations
        OrganizationInvitation.objects.create(
            organization=self.organization,
            email="multi@test.com",
            role="member",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        OrganizationInvitation.objects.create(
            organization=org2,
            email="multi@test.com",
            role="admin",
            status="pending",
            token=secrets.token_urlsafe(32),
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Register
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "multi@test.com",
                "username": "multiuser",
                "first_name": "Multi",
                "last_name": "Org",
                "password": "TestPassword123!",
                "password_confirm": "TestPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["pending_invitations_accepted"], 2)
        self.assertEqual(len(response.data["auto_joined_organizations"]), 2)

        # Verify both memberships created
        user = User.objects.get(email="multi@test.com")
        memberships = OrganizationMembership.objects.filter(user=user)
        self.assertEqual(memberships.count(), 2)
