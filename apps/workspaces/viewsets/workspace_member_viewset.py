import logging

from django.db.models import Prefetch

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workspaces.models import WorkspaceMember
from apps.workspaces.serializers import WorkspaceMemberSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_list",
        summary="List Workspace Members",
        description="List workspace members. Filter by workspace using ?workspace={uuid} query parameter.",  # noqa: E501
        parameters=[
            OpenApiParameter(
                name="workspace",
                type=str,
                location=OpenApiParameter.QUERY,
                description="UUID of the workspace to filter members",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_retrieve",
        summary="Get Workspace Member Details",
    ),
    create=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_create",
        summary="Add Member to Workspace",
    ),
    update=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_update",
        summary="Update Member Role",
    ),
    partial_update=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_partial_update",
        summary="Partial Update Member",
    ),
)
class WorkspaceMemberViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceMemberSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """
        Get workspace members queryset.

        Supports filtering by workspace via query parameter:
        - ?workspace={uuid} - Filter members by workspace ID

        Also supports URL path parameter for nested routes (future):
        - /workspaces/{workspace_id}/members/
        """
        # Handle schema generation and OPTIONS requests
        if (
            getattr(self, "swagger_fake_view", False)
            or self.request.method == "OPTIONS"
        ):
            return WorkspaceMember.objects.all()

        if not self.request.user.is_authenticated:
            return WorkspaceMember.objects.none()

        user = self.request.user

        # CRITICAL FIX: Check query params first (frontend uses this)
        workspace_id = self.request.query_params.get("workspace")

        # Fallback to URL kwargs for nested routes
        if not workspace_id:
            workspace_id = self.kwargs.get("workspace_id")

        # Query optimization to prevent N+1
        queryset = WorkspaceMember.objects.select_related(
            "user", "workspace"
        ).prefetch_related(Prefetch("user__profile"))

        if workspace_id:
            logger.info(f"Filtering workspace members by workspace_id: {workspace_id}")
            queryset = queryset.filter(workspace_id=workspace_id)
        else:
            # No workspace specified - show user's memberships
            logger.debug(
                f"No workspace filter - showing memberships for user: {user.username}"
            )
            queryset = queryset.filter(
                workspace__members__user=user, workspace__members__is_active=True
            ).distinct()

        return queryset.filter(is_active=True).order_by("-joined_at")

    def create(self, request, *args, **kwargs):
        """
        Create a new workspace member.

        Expects:
        - workspace: UUID of workspace
        - user_id: UUID of user to add
        - role: member role (default: 'member')
        """
        logger.info(f"Creating workspace member: {request.data}")

        # Check for duplicate membership
        workspace_id = request.data.get("workspace")
        user_id = request.data.get("user_id")

        if workspace_id and user_id:
            existing = WorkspaceMember.objects.filter(
                workspace_id=workspace_id, user_id=user_id
            ).first()

            if existing:
                if existing.is_active:
                    return Response(
                        {"error": "User is already a member of this workspace"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    # Reactivate inactive membership
                    existing.is_active = True
                    existing.role = request.data.get("role", existing.role)
                    existing.save()
                    serializer = self.get_serializer(existing)
                    return Response(serializer.data, status=status.HTTP_200_OK)

        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_update_role",
        summary="Update Member Role",
    )
    @action(detail=True, methods=["patch"], url_path="update-role")
    def update_role(self, request, pk=None):
        member = self.get_object()
        new_role = request.data.get("role")

        if new_role not in dict(WorkspaceMember.ROLE_CHOICES):
            return Response(
                {"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST
            )

        member.role = new_role
        member.save()

        serializer = self.get_serializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)
