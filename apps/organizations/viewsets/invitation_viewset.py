"""
ViewSet for organization invitation management.
Handles invitation creation, verification, acceptance, and revocation.
"""
from django.db import transaction

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.organizations.models import Organization, OrganizationInvitation
from apps.organizations.serializers import (
    OrganizationInvitationAcceptSerializer,
    OrganizationInvitationCreateSerializer,
    OrganizationInvitationDetailSerializer,
    OrganizationInvitationVerifySerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Organizations"],
        operation_id="organization_invitations_list",
        summary="List Organization Invitations",
        description="List all invitations for an organization. Requires owner/admin/manager role.",
        parameters=[
            OpenApiParameter(
                name="organization",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Organization UUID to filter invitations",
                required=True,
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by status (pending, accepted, expired, revoked)",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Organizations"],
        operation_id="organization_invitations_retrieve",
        summary="Get Invitation Details",
    ),
    destroy=extend_schema(
        tags=["Organizations"],
        operation_id="organization_invitations_revoke",
        summary="Revoke Invitation",
        description="Revoke/cancel a pending invitation. Only owner/admin or inviter can revoke.",
    ),
)
class OrganizationInvitationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization invitations.

    Supports:
    - Creating invitations by email
    - Verifying invitation tokens
    - Accepting invitations
    - Listing pending invitations
    - Revoking invitations
    """

    serializer_class = OrganizationInvitationDetailSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        """Return invitations accessible by the requesting user."""
        if getattr(self, "swagger_fake_view", False):
            return OrganizationInvitation.objects.none()

        queryset = OrganizationInvitation.objects.select_related(
            "organization", "invited_by"
        ).all()

        # Filter by organization if provided
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)

        # Filter by status if provided
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Only show invitations from organizations where user is a member
        queryset = queryset.filter(
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True,
        ).distinct()

        return queryset

    @extend_schema(
        tags=["Organizations"],
        operation_id="organization_invitations_create",
        summary="Invite User by Email",
        description=(
            "Invite a user to join an organization by email. "
            "If user exists: creates membership directly and sends notification. "
            "If user doesn't exist: creates pending invitation and sends invitation email with token. "
            "Requires owner/admin/manager role in the organization."
        ),
        request=OrganizationInvitationCreateSerializer,
        responses={
            201: OrganizationInvitationCreateSerializer,
            400: {"description": "Validation errors"},
        },
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create invitation or add member directly if user exists."""
        serializer = OrganizationInvitationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Organizations"],
        operation_id="organization_invitations_verify",
        summary="Verify Invitation Token",
        description=(
            "Verify an invitation token before user registration. "
            "Returns invitation details including organization info and pre-filled email. "
            "This endpoint is PUBLIC (no authentication required) to support the registration flow."
        ),
        parameters=[
            OpenApiParameter(
                name="token",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Invitation token from email link",
                required=True,
            )
        ],
        responses={
            200: {
                "description": "Valid invitation",
                "example": {
                    "valid": True,
                    "email": "user@example.com",
                    "organization": {
                        "id": "uuid",
                        "name": "ACME Corp",
                        "logo": "url",
                    },
                    "role": "member",
                    "role_display": "Member",
                    "invited_by": {"full_name": "John Doe"},
                    "expires_at": "2025-10-17T14:00:00Z",
                    "days_remaining": 5,
                },
            },
            400: {"description": "Invalid or expired token"},
        },
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="verify",
    )
    def verify(self, request):
        """
        Verify invitation token (PUBLIC endpoint).
        Used before user registration to validate token and get invitation details.
        """
        token = request.query_params.get("token")

        if not token:
            return Response(
                {"valid": False, "error": "Token parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrganizationInvitationVerifySerializer(
            data={"token": token}, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(
                {
                    "valid": False,
                    "error": serializer.errors.get("token", ["Invalid token"])[0],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation_data = serializer.get_invitation_data()
        return Response(invitation_data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Organizations"],
        operation_id="organization_invitations_accept",
        summary="Accept Invitation",
        description=(
            "Accept an organization invitation using the token. "
            "User must be authenticated and their email must match the invitation email. "
            "Creates organization membership and sends welcome email."
        ),
        request=OrganizationInvitationAcceptSerializer,
        responses={
            200: {
                "description": "Invitation accepted successfully",
                "example": {
                    "success": True,
                    "organization": {"id": "uuid", "name": "ACME Corp"},
                    "role": "member",
                    "role_display": "Member",
                    "message": "Te has unido a ACME Corp exitosamente",
                    "redirect_url": "/organizations/uuid/dashboard",
                },
            },
            400: {"description": "Invalid token, expired, or email mismatch"},
        },
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="accept",
    )
    @transaction.atomic
    def accept(self, request):
        """Accept invitation and create membership."""
        serializer = OrganizationInvitationAcceptSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Revoke an invitation."""
        invitation = self.get_object()

        # Check permissions: only owner/admin or the inviter can revoke
        from apps.organizations.models import OrganizationMembership

        membership = OrganizationMembership.objects.filter(
            organization=invitation.organization,
            user=request.user,
            is_active=True,
        ).first()

        can_revoke = False
        if membership and membership.role in ["owner", "admin"]:
            can_revoke = True
        elif invitation.invited_by == request.user:
            can_revoke = True

        if not can_revoke:
            return Response(
                {"error": "No tienes permiso para revocar esta invitación"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            invitation.revoke()

            # Log action
            from apps.logging.services import LoggerService

            LoggerService.log_info(
                action="organization_invitation_revoked",
                user=request.user,
                details={
                    "invitation_id": str(invitation.id),
                    "organization_id": str(invitation.organization.id),
                    "invited_email": invitation.email,
                },
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
