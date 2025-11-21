from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
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
        queryset = (
            Workspace.objects.filter(
                members__user=self.request.user, members__is_active=True
            )
            .select_related("organization", "created_by")
            .distinct()
        )

        if self.action == "list":
            week_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.annotate(
                active_projects_count=Count(
                    "projects",
                    filter=Q(projects__status="active"),
                    distinct=True,
                ),
                team_members_count=Count(
                    "members",
                    filter=Q(members__is_active=True),
                    distinct=True,
                ),
                prev_active_projects=Count(
                    "projects",
                    filter=Q(
                        projects__status="active",
                        projects__created_at__lte=week_ago,
                    ),
                    distinct=True,
                ),
                prev_team_members=Count(
                    "members",
                    filter=Q(
                        members__is_active=True,
                        members__joined_at__lte=week_ago,
                    ),
                    distinct=True,
                ),
            )
        else:
            queryset = queryset.prefetch_related("members", "members__user", "projects")

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_serializer(self, *args, **kwargs):
        """Enhanced serializer with intelligent content-type handling."""
        # Add request context for validation
        kwargs["context"] = kwargs.get("context", {})
        kwargs["context"]["request"] = self.request

        # Add global stats for list action
        if self.action == "list":
            kwargs["context"]["global_stats"] = self._get_global_stats()

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

    def _get_global_stats(self):
        """Calculate global statistics once for all items in list."""
        user = self.request.user
        week_ago = timezone.now() - timedelta(days=7)

        workspaces = Workspace.objects.filter(
            members__user=user, members__is_active=True
        ).distinct()

        current_count = workspaces.count()
        previous_count = workspaces.filter(created_at__lte=week_ago).count()

        return {
            "workspaces_change_pct": self._calc_pct(current_count, previous_count),
        }

    def _calc_pct(self, current, previous):
        """Calculate percentage change between two values."""
        if previous and previous > 0:
            return int(((current - previous) / previous) * 100)
        return 100 if current and current > 0 else 0

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
        members = (
            WorkspaceMember.objects.filter(workspace=workspace, is_active=True)
            .select_related("user", "workspace")
            .order_by("-joined_at")
        )

        serializer = WorkspaceMemberSerializer(
            members, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="workspaces_dashboard_stats",
        summary="Get Dashboard Statistics",
        description=(
            "Aggregated statistics across all workspaces user has access to. "
            "Includes percentage changes compared to 7 days ago. "
            "Optimized with single query using annotations."
        ),
    )
    @action(detail=False, methods=["get"], url_path="dashboard-stats")
    def dashboard_stats(self, request):
        """Return dashboard statistics optimized with annotations."""
        user = request.user
        week_ago = timezone.now() - timedelta(days=7)

        workspaces = Workspace.objects.filter(
            members__user=user, members__is_active=True
        ).distinct()

        current_stats = workspaces.aggregate(
            total_active_projects=Count(
                "projects",
                filter=Q(projects__status="active"),
                distinct=True,
            ),
            total_team_members=Count(
                "members", filter=Q(members__is_active=True), distinct=True
            ),
            total_workspaces=Count("id", distinct=True),
        )

        previous_stats = workspaces.aggregate(
            prev_projects=Count(
                "projects",
                filter=Q(
                    projects__status="active",
                    projects__created_at__lte=week_ago,
                ),
                distinct=True,
            ),
            prev_members=Count(
                "members",
                filter=Q(
                    members__is_active=True,
                    members__joined_at__lte=week_ago,
                ),
                distinct=True,
            ),
            prev_workspaces=Count(
                "id", filter=Q(created_at__lte=week_ago), distinct=True
            ),
        )

        return Response(
            {
                "active_projects": current_stats["total_active_projects"] or 0,
                "active_projects_change_pct": self._calc_pct(
                    current_stats["total_active_projects"],
                    previous_stats["prev_projects"],
                ),
                "team_members": current_stats["total_team_members"] or 0,
                "team_members_change_pct": self._calc_pct(
                    current_stats["total_team_members"],
                    previous_stats["prev_members"],
                ),
                "total_workspaces": current_stats["total_workspaces"] or 0,
                "total_workspaces_change_pct": self._calc_pct(
                    current_stats["total_workspaces"],
                    previous_stats["prev_workspaces"],
                ),
            },
            status=status.HTTP_200_OK,
        )
