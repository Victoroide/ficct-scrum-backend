from django.db import transaction

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workspaces.models import Workspace, WorkspaceMember
from apps.workspaces.permissions import (
    CanAccessWorkspace,
    IsWorkspaceAdmin,
    IsWorkspaceMember,
)
from apps.workspaces.serializers import WorkspaceMemberSerializer, WorkspaceSerializer
from base.utils.file_handlers import upload_workspace_asset_to_s3


@extend_schema_view(
    list=extend_schema(
        tags=["Workspaces"], operation_id="workspaces_list", summary="List Workspaces"
    ),
    retrieve=extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_retrieve",
        summary="Get Workspace Details",
    ),
    create=extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_create",
        summary="Create Workspace",
    ),
    update=extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_update",
        summary="Update Workspace",
    ),
    partial_update=extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_partial_update",
        summary="Partial Update Workspace",
    ),
    destroy=extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_destroy",
        summary="Delete Workspace",
    ),
)
class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        """Assign permissions based on action."""
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsWorkspaceAdmin()]
        elif self.action in ["retrieve", "list"]:
            return [IsAuthenticated(), CanAccessWorkspace()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return Workspace.objects.filter(
            members__user=self.request.user, members__is_active=True
        ).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_serializer(self, *args, **kwargs):
        """Enhanced serializer with intelligent content-type handling."""
        # Add request context for validation
        kwargs["context"] = kwargs.get("context", {})
        kwargs["context"]["request"] = self.request

        # Handle both JSON and multipart data formats
        if self.request.method == "POST" and hasattr(self.request, "data"):
            # Normalize organization field for both JSON and multipart
            data = (
                self.request.data.copy()
                if hasattr(self.request.data, "copy")
                else dict(self.request.data)
            )

            # Handle organization field from either format
            if "organization" in data:
                # Ensure organization is properly formatted as UUID string
                try:
                    import uuid

                    if isinstance(data["organization"], str):
                        # Validate UUID format
                        uuid.UUID(data["organization"])
                    kwargs["data"] = data
                except (ValueError, TypeError):
                    # Invalid UUID format, let serializer validation handle it
                    pass

        return super().get_serializer(*args, **kwargs)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_upload_cover",
        summary="Upload Workspace Cover Image",
    )
    @action(detail=True, methods=["post"], url_path="upload-cover")
    def upload_cover(self, request, pk=None):
        workspace = self.get_object()
        if "cover_image" not in request.FILES:
            return Response(
                {"error": "No cover image file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cover_file = request.FILES["cover_image"]
        try:
            cover_path = upload_workspace_asset_to_s3(cover_file, workspace.id)
            workspace.cover_image = cover_path
            workspace.save()
            return Response(
                {"cover_image_url": workspace.cover_image.url},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_members_list",
        summary="List Workspace Members",
        description="Retrieve a list of all active members for the given workspace.",
    )
    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        """Retrieve a list of members for the given workspace."""
        workspace = self.get_object()
        
        # Query optimization to prevent N+1
        members = WorkspaceMember.objects.filter(
            workspace=workspace,
            is_active=True
        ).select_related(
            'user',
            'workspace'
        ).order_by('-joined_at')
        
        serializer = WorkspaceMemberSerializer(
            members,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
