import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.organizations.models import (
    OrganizationInvitation,
    OrganizationMembership,
)
from apps.organizations.permissions import CanManageMembers
from apps.organizations.serializers import OrganizationMemberSerializer
from base.services import EmailService

logger = logging.getLogger(__name__)


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
            "**NEW:** Sends invitation email via AWS SES with accept link (expires in 7 days). "  # noqa: E501
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
        """
        Optimized queryset with select_related and prefetch_related.
        Supports filtering by organization via query parameter.
        """
        # Handle schema generation
        if getattr(self, "swagger_fake_view", False):
            return OrganizationMembership.objects.none()

        try:
            # Query optimization to prevent N+1
            queryset = OrganizationMembership.objects.select_related(
                "user", "organization", "invited_by"
            ).prefetch_related(Prefetch("user__profile"))

            # Filter by organization if provided (critical for frontend)
            organization_id = self.request.query_params.get("organization")
            if organization_id:
                queryset = queryset.filter(organization_id=organization_id)
            else:
                # If no org specified, show memberships from orgs where user is member
                queryset = queryset.filter(
                    organization__memberships__user=self.request.user,
                    organization__memberships__is_active=True,
                ).distinct()

            return queryset.order_by("-joined_at")

        except Exception as e:
            logger.error(f"Error in get_queryset: {str(e)}", exc_info=True)
            return OrganizationMembership.objects.none()

    def list(self, request, *args, **kwargs):
        """List members with robust error handling."""
        try:
            organization_id = request.query_params.get("organization")
            logger.info(
                f"Listing members for organization: {organization_id}, user: {request.user.username}"  # noqa: E501
            )

            queryset = self.filter_queryset(self.get_queryset())
            count = queryset.count()
            logger.debug(f"Found {count} members")

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Error listing organization members: {str(e)}", exc_info=True)
            return Response(
                {
                    "error": "Error al cargar miembros de la organización",
                    "detail": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve member with error handling."""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error retrieving member: {str(e)}", exc_info=True)
            return Response(
                {"error": "Error al obtener miembro", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
