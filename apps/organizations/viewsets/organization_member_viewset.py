import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.models import User
from apps.logging.services import LoggerService
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from apps.organizations.permissions import CanManageMembers
from apps.organizations.serializers import OrganizationMemberSerializer
from base.services import EmailService


@extend_schema_view(
    list=extend_schema(
        tags=["Organizations"],
        operation_id="organization_members_list",
        summary="List Organization Members",
    ),
    retrieve=extend_schema(
        tags=["Organizations"],
        operation_id="organization_members_retrieve",
        summary="Get Organization Member Details",
    ),
    create=extend_schema(
        tags=["Organizations"],
        operation_id="organization_members_create",
        summary="Invite Member to Organization",
        description=(
            "**NEW:** Sends invitation email via AWS SES with accept link (expires in 7 days). "
            "Email delivery failures are logged but do not block membership creation. "
            "Requires permission: Owner, Admin, or Manager can invite members."
        ),
    ),
    update=extend_schema(
        tags=["Organizations"],
        operation_id="organization_members_update",
        summary="Update Member Role",
    ),
    partial_update=extend_schema(
        tags=["Organizations"],
        operation_id="organization_members_partial_update",
        summary="Partial Update Member",
    ),
    destroy=extend_schema(
        tags=["Organizations"],
        operation_id="organization_members_destroy",
        summary="Remove Member from Organization",
    ),
)
class OrganizationMemberViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationMemberSerializer
    permission_classes = [IsAuthenticated, CanManageMembers]

    def get_queryset(self):
        # Handle schema generation
        if getattr(self, "swagger_fake_view", False):
            return OrganizationMembership.objects.none()
            
        return OrganizationMembership.objects.filter(
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True,
        ).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        membership = serializer.save(invited_by=self.request.user)

        # Create invitation token and send email
        try:
            invitation_token = secrets.token_urlsafe(32)
            invitation, created = OrganizationInvitation.objects.get_or_create(
                organization=membership.organization,
                email=membership.user.email,
                defaults={
                    "role": membership.role,
                    "status": "pending",
                    "token": invitation_token,
                    "invited_by": self.request.user,
                    "expires_at": timezone.now() + timedelta(days=7),
                },
            )

            # Send invitation email
            try:
                EmailService.send_organization_invitation_email(
                    invitation=invitation,
                    invited_by_name=self.request.user.full_name,
                )
            except Exception as email_error:
                LoggerService.log_error(
                    action="organization_invitation_email_failed",
                    user=self.request.user,
                    ip_address=self.request.META.get("REMOTE_ADDR"),
                    error=str(email_error),
                )
        except Exception as e:
            LoggerService.log_error(
                action="organization_invitation_creation_failed",
                user=self.request.user,
                error=str(e),
            )

    @extend_schema(
        tags=["Organizations"],
        operation_id="organization_members_update_role",
        summary="Update Member Role",
    )
    @action(detail=True, methods=["patch"], url_path="update-role")
    def update_role(self, request, pk=None):
        membership = self.get_object()
        new_role = request.data.get("role")

        if new_role not in dict(OrganizationMembership.ROLE_CHOICES):
            return Response(
                {"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST
            )

        membership.role = new_role
        membership.save()

        serializer = self.get_serializer(membership)
        return Response(serializer.data, status=status.HTTP_200_OK)
