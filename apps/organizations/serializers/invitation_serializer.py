"""
Serializers for organization invitation system.
Handles email-based invitations for both existing and new users.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.authentication.models import User
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from base.serializers import OrganizationBasicSerializer, UserBasicSerializer


class OrganizationInvitationCreateSerializer(serializers.Serializer):
    """
    Serializer for creating invitations by email.
    Handles both existing users (creates membership directly) and new users (creates invitation).
    """

    organization = serializers.UUIDField(write_only=True)
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=OrganizationMembership.ROLE_CHOICES, default="member"
    )
    message = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_email(self, value):
        """Validate email format."""
        return value.lower().strip()

    def validate(self, attrs):
        """Validate that invitation can be created."""
        organization_id = attrs.get("organization")
        email = attrs.get("email")
        request = self.context.get("request")

        # Get organization
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise serializers.ValidationError(
                {"organization": "Organization not found"}
            )

        # Check if requesting user is a member with permission to invite
        membership = OrganizationMembership.objects.filter(
            organization=organization, user=request.user, is_active=True
        ).first()

        if not membership:
            raise serializers.ValidationError(
                {"organization": "You are not a member of this organization"}
            )

        if membership.role not in ["owner", "admin", "manager"]:
            raise serializers.ValidationError(
                {"organization": "You don't have permission to invite members"}
            )

        # Check if user with this email already exists and is a member
        try:
            user = User.objects.get(email=email)
            if OrganizationMembership.objects.filter(
                organization=organization, user=user, is_active=True
            ).exists():
                raise serializers.ValidationError(
                    {"email": "User is already a member of this organization"}
                )
        except User.DoesNotExist:
            pass

        # Check if pending invitation already exists
        if OrganizationInvitation.objects.filter(
            organization=organization, email=email, status="pending"
        ).exists():
            raise serializers.ValidationError(
                {"email": "A pending invitation already exists for this email"}
            )

        # Store organization in context for create method
        attrs["_organization"] = organization
        attrs["_membership"] = membership

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """
        Create invitation or membership depending on user existence.
        
        Returns:
            dict: Response data with status and details
        """
        email = validated_data["email"]
        organization = validated_data["_organization"]
        role = validated_data["role"]
        message = validated_data.get("message", "")
        inviting_membership = validated_data["_membership"]
        request = self.context.get("request")

        # Check if user exists
        try:
            user = User.objects.get(email=email)
            user_exists = True
        except User.DoesNotExist:
            user = None
            user_exists = False

        if user_exists:
            # USER EXISTS: Create membership directly
            membership = OrganizationMembership.objects.create(
                organization=organization,
                user=user,
                role=role,
                status="active",
                invited_by=request.user,
                joined_at=timezone.now(),
            )

            # Send notification email
            from base.services import EmailService

            try:
                EmailService.send_organization_member_added_email(
                    user=user,
                    organization=organization,
                    role=role,
                    invited_by_name=request.user.full_name,
                )
            except Exception:
                pass  # Email failure shouldn't block membership creation

            # Log action
            from apps.logging.services import LoggerService

            LoggerService.log_info(
                action="organization_member_added_directly",
                user=request.user,
                details={
                    "organization_id": str(organization.id),
                    "added_user_email": email,
                    "role": role,
                },
            )

            return {
                "id": str(membership.id),
                "user": UserBasicSerializer(user).data,
                "organization": str(organization.id),
                "role": role,
                "status": "accepted",
                "joined_at": membership.joined_at.isoformat(),
                "message": "Usuario agregado a la organización",
                "user_existed": True,
            }

        else:
            # USER DOESN'T EXIST: Create invitation
            invitation = OrganizationInvitation.objects.create(
                organization=organization,
                email=email,
                role=role,
                status="pending",
                token=secrets.token_urlsafe(32),
                invited_by=request.user,
                message=message,
                expires_at=timezone.now() + timedelta(days=7),
            )

            # Send invitation email
            email_sent = invitation.send_invitation_email()

            # Log action
            from apps.logging.services import LoggerService

            LoggerService.log_info(
                action="organization_invitation_created",
                user=request.user,
                details={
                    "organization_id": str(organization.id),
                    "invitation_id": str(invitation.id),
                    "invited_email": email,
                    "role": role,
                    "email_sent": email_sent,
                },
            )

            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:4200")
            acceptance_url = f"{frontend_url}/accept-invitation?token={invitation.token}"

            return {
                "id": str(invitation.id),
                "email": email,
                "organization": str(organization.id),
                "role": role,
                "status": "pending",
                "invitation_sent": email_sent,
                "expires_at": invitation.expires_at.isoformat(),
                "acceptance_url": acceptance_url,
                "message": "Invitación enviada por email",
                "user_existed": False,
            }


class OrganizationInvitationDetailSerializer(serializers.ModelSerializer):
    """Detailed read-only serializer for invitations."""

    organization = OrganizationBasicSerializer(read_only=True)
    invited_by = UserBasicSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_remaining = serializers.SerializerMethodField()
    acceptance_url = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "organization",
            "email",
            "role",
            "role_display",
            "status",
            "invited_by",
            "message",
            "expires_at",
            "accepted_at",
            "is_expired",
            "days_remaining",
            "acceptance_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_days_remaining(self, obj):
        """Get days until expiration."""
        return obj.days_until_expiry

    def get_acceptance_url(self, obj):
        """Generate acceptance URL."""
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:4200")
        return f"{frontend_url}/accept-invitation?token={obj.token}"


class OrganizationInvitationVerifySerializer(serializers.Serializer):
    """
    Serializer for verifying invitation tokens.
    Used before user registration to pre-fill email.
    """

    token = serializers.CharField()

    def validate_token(self, value):
        """Validate that token exists and is valid."""
        try:
            invitation = OrganizationInvitation.objects.get(
                token=value, status="pending"
            )

            if invitation.is_expired:
                raise serializers.ValidationError("Invitación expirada")

            # Store invitation in context for retrieval
            self.context["invitation"] = invitation
            return value

        except OrganizationInvitation.DoesNotExist:
            raise serializers.ValidationError("Token de invitación inválido")

    def get_invitation_data(self):
        """Return validated invitation data."""
        invitation = self.context.get("invitation")
        if not invitation:
            return None

        return {
            "valid": True,
            "email": invitation.email,
            "organization": OrganizationBasicSerializer(invitation.organization).data,
            "role": invitation.role,
            "role_display": invitation.get_role_display(),
            "invited_by": UserBasicSerializer(invitation.invited_by).data,
            "expires_at": invitation.expires_at.isoformat(),
            "days_remaining": invitation.days_until_expiry,
            "message": invitation.message,
        }


class OrganizationInvitationAcceptSerializer(serializers.Serializer):
    """
    Serializer for accepting invitations.
    Requires authenticated user whose email matches the invitation.
    """

    token = serializers.CharField()

    def validate_token(self, value):
        """Validate token and check user email match."""
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Debe estar autenticado para aceptar invitaciones")

        try:
            invitation = OrganizationInvitation.objects.get(
                token=value, status="pending"
            )
        except OrganizationInvitation.DoesNotExist:
            raise serializers.ValidationError("Token de invitación inválido")

        if invitation.is_expired:
            raise serializers.ValidationError("La invitación ha expirado")

        if request.user.email != invitation.email:
            raise serializers.ValidationError(
                "El email de tu cuenta no coincide con el email de la invitación"
            )

        # Check if user is already a member
        if OrganizationMembership.objects.filter(
            organization=invitation.organization, user=request.user, is_active=True
        ).exists():
            raise serializers.ValidationError(
                "Ya eres miembro de esta organización"
            )

        # Store invitation for create method
        self.context["invitation"] = invitation
        return value

    @transaction.atomic
    def save(self):
        """Accept invitation and create membership."""
        invitation = self.context["invitation"]
        request = self.context["request"]

        # Use the model's accept method
        membership = invitation.accept(request.user)

        # Send welcome email
        from base.services import EmailService

        try:
            EmailService.send_organization_welcome_email(
                user=request.user,
                organization=invitation.organization,
                role=invitation.role,
            )
        except Exception:
            pass  # Email failure shouldn't block acceptance

        # Log action
        from apps.logging.services import LoggerService

        LoggerService.log_info(
            action="organization_invitation_accepted",
            user=request.user,
            details={
                "organization_id": str(invitation.organization.id),
                "invitation_id": str(invitation.id),
                "role": invitation.role,
            },
        )

        return {
            "success": True,
            "organization": OrganizationBasicSerializer(invitation.organization).data,
            "role": invitation.role,
            "role_display": invitation.get_role_display(),
            "message": f"Te has unido a {invitation.organization.name} exitosamente",
            "redirect_url": f"/organizations/{invitation.organization.id}/dashboard",
            "membership_id": str(membership.id),
        }
