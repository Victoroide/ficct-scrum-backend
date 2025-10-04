import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.authentication.serializers import UserSerializer
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    Workspace,
    WorkspaceMembership,
)


class OrganizationSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    member_count = serializers.ReadOnlyField()
    workspace_count = serializers.ReadOnlyField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo",
            "website_url",
            "organization_type",
            "subscription_plan",
            "owner",
            "organization_settings",
            "is_active",
            "member_count",
            "workspace_count",
            "user_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_user_role(self, obj) -> str:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            try:
                membership = OrganizationMembership.objects.get(
                    organization=obj, user=request.user, is_active=True
                )
                return membership.role
            except OrganizationMembership.DoesNotExist:
                return None
        return None

    def validate_slug(self, value):
        if self.instance:
            if (
                Organization.objects.exclude(id=self.instance.id)
                .filter(slug=value)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Organization with this slug already exists"
                )
        else:
            if Organization.objects.filter(slug=value).exists():
                raise serializers.ValidationError(
                    "Organization with this slug already exists"
                )
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["owner"] = request.user

        organization = Organization.objects.create(**validated_data)

        # Create owner membership
        OrganizationMembership.objects.create(
            organization=organization,
            user=request.user,
            role="owner",
            status="active",
            joined_at=timezone.now(),
        )

        return organization


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    invited_by = UserSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            "id",
            "organization",
            "user",
            "role",
            "status",
            "permissions",
            "invited_by",
            "invited_at",
            "joined_at",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "user",
            "invited_by",
            "invited_at",
            "joined_at",
            "created_at",
            "updated_at",
        ]


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    invited_by = UserSerializer(read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "organization",
            "email",
            "role",
            "status",
            "invited_by",
            "message",
            "expires_at",
            "accepted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "invited_by",
            "status",
            "expires_at",
            "accepted_at",
            "created_at",
            "updated_at",
        ]

    def validate_email(self, value):
        organization = self.context.get("organization")
        if organization:
            # Check if user is already a member
            from apps.authentication.models import User

            try:
                user = User.objects.get(email=value)
                if OrganizationMembership.objects.filter(
                    organization=organization, user=user, is_active=True
                ).exists():
                    raise serializers.ValidationError(
                        "User is already a member of this organization"
                    )
            except User.DoesNotExist:
                pass

            # Check if invitation already exists
            if OrganizationInvitation.objects.filter(
                organization=organization, email=value, status="pending"
            ).exists():
                raise serializers.ValidationError(
                    "Invitation already sent to this email"
                )

        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        organization = self.context.get("organization")

        validated_data["organization"] = organization
        validated_data["invited_by"] = request.user
        validated_data["token"] = secrets.token_urlsafe(32)
        validated_data["expires_at"] = timezone.now() + timedelta(days=7)

        invitation = OrganizationInvitation.objects.create(**validated_data)

        # Send invitation email
        invitation_url = f"{settings.FRONTEND_URL}/invitations/{invitation.token}"
        send_mail(
            subject=f"Invitation to join {organization.name}",
            message=f"You have been invited to join {organization.name}. Click here to accept: {invitation_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )

        return invitation


class WorkspaceSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    member_count = serializers.ReadOnlyField()
    project_count = serializers.ReadOnlyField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id",
            "organization",
            "name",
            "slug",
            "description",
            "workspace_type",
            "visibility",
            "workspace_settings",
            "is_active",
            "created_by",
            "member_count",
            "project_count",
            "user_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_user_role(self, obj) -> str:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            try:
                membership = WorkspaceMembership.objects.get(
                    workspace=obj, user=request.user, is_active=True
                )
                return membership.role
            except WorkspaceMembership.DoesNotExist:
                return None
        return None

    def validate_slug(self, value):
        organization = self.context.get("organization")
        if self.instance:
            if (
                Workspace.objects.exclude(id=self.instance.id)
                .filter(organization=organization, slug=value)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Workspace with this slug already exists in this organization"
                )
        else:
            if Workspace.objects.filter(organization=organization, slug=value).exists():
                raise serializers.ValidationError(
                    "Workspace with this slug already exists in this organization"
                )
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        organization = self.context.get("organization")

        validated_data["organization"] = organization
        validated_data["created_by"] = request.user

        workspace = Workspace.objects.create(**validated_data)

        # Create admin membership for creator
        WorkspaceMembership.objects.create(
            workspace=workspace, user=request.user, role="admin"
        )

        return workspace


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    workspace = WorkspaceSerializer(read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = [
            "id",
            "workspace",
            "user",
            "role",
            "permissions",
            "is_active",
            "joined_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "user", "joined_at", "updated_at"]


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        try:
            invitation = OrganizationInvitation.objects.get(
                token=value, status="pending"
            )
            if invitation.is_expired:
                raise serializers.ValidationError("Invitation has expired")
            return value
        except OrganizationInvitation.DoesNotExist:
            raise serializers.ValidationError("Invalid invitation token")

    @transaction.atomic
    def save(self):
        token = self.validated_data["token"]
        request = self.context.get("request")

        invitation = OrganizationInvitation.objects.get(token=token)

        # Create or update membership
        membership, created = OrganizationMembership.objects.get_or_create(
            organization=invitation.organization,
            user=request.user,
            defaults={
                "role": invitation.role,
                "status": "active",
                "invited_by": invitation.invited_by,
                "joined_at": timezone.now(),
            },
        )

        if not created:
            membership.role = invitation.role
            membership.status = "active"
            membership.joined_at = timezone.now()
            membership.is_active = True
            membership.save()

        # Mark invitation as accepted
        invitation.status = "accepted"
        invitation.accepted_at = timezone.now()
        invitation.save()

        return membership
