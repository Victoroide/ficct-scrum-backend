import logging
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Project
from apps.projects.permissions import (
    CanAccessProject,
    IsProjectLeadOrAdmin,
)
from apps.projects.serializers import ProjectSerializer
from base.utils.file_handlers import upload_project_file_to_s3

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=["Projects"],
        operation_id="projects_list",
        summary="List Projects",
        description=(
            "Returns projects where the authenticated user is a workspace member. "
            "Supports filtering by workspace and organization."
        ),
        parameters=[
            OpenApiParameter(
                name="workspace",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter projects by workspace UUID",
                required=False,
            ),
            OpenApiParameter(
                name="organization",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter projects by organization UUID",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Projects"],
        operation_id="projects_retrieve",
        summary="Get Project Details",
    ),
    create=extend_schema(
        tags=["Projects"],
        operation_id="projects_create",
        summary="Create Project",
        description=(
            "**MAJOR CHANGE:** Automatically creates 3 default workflow statuses: "
            "'To Do' (initial), 'In Progress', 'Done' (final). "
            "Creator is automatically assigned as project lead. "
            "Frontend must fetch workflow statuses immediately after creation "
            "and should NOT manually create statuses."
        ),
    ),
    update=extend_schema(
        tags=["Projects"], operation_id="projects_update", summary="Update Project"
    ),
    partial_update=extend_schema(
        tags=["Projects"],
        operation_id="projects_partial_update",
        summary="Partial Update Project",
    ),
    destroy=extend_schema(
        tags=["Projects"], operation_id="projects_destroy", summary="Delete Project"
    ),
)
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Assign permissions based on action."""
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsProjectLeadOrAdmin()]
        elif self.action in ["retrieve", "list"]:
            return [IsAuthenticated(), CanAccessProject()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        Filter projects based on user membership and query parameters.

        Query Parameters:
            - workspace: UUID of workspace to filter by
            - organization: UUID of organization to filter by

        Returns only projects where user is a workspace member.
        """
        # Base queryset: user must be a member of the workspace
        queryset = Project.objects.filter(
            workspace__members__user=self.request.user,
            workspace__members__is_active=True,
        ).select_related(
            "workspace", "workspace__organization", "lead", "created_by"
        ).distinct()

        if self.action == "list":
            week_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.annotate(
                team_members_count=Count(
                    "team_members",
                    filter=Q(team_members__is_active=True),
                    distinct=True,
                ),
                active_issues_count=Count(
                    "issues",
                    filter=Q(issues__is_active=True),
                    distinct=True,
                ),
                prev_team_members=Count(
                    "team_members",
                    filter=Q(
                        team_members__is_active=True,
                        team_members__joined_at__lte=week_ago,
                    ),
                    distinct=True,
                ),
                prev_issues=Count(
                    "issues",
                    filter=Q(
                        issues__is_active=True,
                        issues__created_at__lte=week_ago,
                    ),
                    distinct=True,
                ),
            )
        else:
            queryset = queryset.prefetch_related(
                "team_members", "team_members__user"
            )

        # Apply filters after annotations to avoid conflicts
        workspace_id = self.request.query_params.get("workspace")
        if workspace_id:
            try:
                # Validate UUID format
                UUID(workspace_id)

                # Apply workspace filter
                queryset = queryset.filter(workspace_id=workspace_id)

                logger.info(
                    f"[PROJECT FILTER] User {self.request.user.email} filtering by workspace: {workspace_id}, "  # noqa: E501
                    f"Result count: {queryset.count()}"
                )

            except ValueError:
                logger.warning(
                    f"[PROJECT FILTER] Invalid workspace UUID format: {workspace_id} "
                    f"from user {self.request.user.email}"
                )
                raise ValidationError(
                    {"workspace": "Invalid workspace ID format. Must be a valid UUID."}
                )

        # Filter by organization if provided
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            try:
                # Validate UUID format
                UUID(organization_id)

                # Apply organization filter
                queryset = queryset.filter(workspace__organization_id=organization_id)

                logger.info(
                    f"[PROJECT FILTER] User {self.request.user.email} filtering by organization: {organization_id}, "  # noqa: E501
                    f"Result count: {queryset.count()}"
                )

            except ValueError:
                logger.warning(
                    f"[PROJECT FILTER] Invalid organization UUID format: {organization_id} "  # noqa: E501
                    f"from user {self.request.user.email}"
                )
                raise ValidationError(
                    {
                        "organization": "Invalid organization ID format. Must be a valid UUID."  # noqa: E501
                    }
                )

        return queryset

    def get_serializer_context(self):
        """Add global stats to context for list action."""
        context = super().get_serializer_context()
        if self.action == "list":
            context["global_stats"] = self._get_global_stats()
        return context

    def _get_global_stats(self):
        """Calculate global statistics once for all items in list."""
        user = self.request.user
        week_ago = timezone.now() - timedelta(days=7)

        projects = Project.objects.filter(
            workspace__members__user=user,
            workspace__members__is_active=True,
        ).distinct()

        current_count = projects.count()
        previous_count = projects.filter(created_at__lte=week_ago).count()

        return {
            "projects_change_pct": self._calc_pct(current_count, previous_count),
        }

    def _calc_pct(self, current, previous):
        """Calculate percentage change between two values."""
        if previous and previous > 0:
            return int(((current - previous) / previous) * 100)
        return 100 if current and current > 0 else 0

    @transaction.atomic
    def perform_create(self, serializer):
        # Create project with creator as lead
        project = serializer.save(created_by=self.request.user, lead=self.request.user)

        # Note: Default workflow statuses, issue types, transitions, and configuration
        # are automatically created by signals in apps/projects/signals.py
        # No manual creation needed here to avoid duplicates

        LoggerService.log_info(
            action="project_created_with_workflows",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(project.id),
                "project_key": project.key,
                "project_name": project.name,
                "workspace_id": str(project.workspace.id),
            },
        )

    @extend_schema(
        tags=["Projects"],
        operation_id="projects_upload_attachment",
        summary="Upload Project Attachment",
    )
    @action(detail=True, methods=["post"], url_path="upload-attachment")
    def upload_attachment(self, request, pk=None):
        project = self.get_object()
        if "attachment" not in request.FILES:
            return Response(
                {"error": "No attachment file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attachment_file = request.FILES["attachment"]
        try:
            attachment_path = upload_project_file_to_s3(attachment_file, project.id)
            project.attachments = attachment_path
            project.save()
            return Response(
                {"attachment_url": project.attachments.url}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Projects"],
        operation_id="projects_dashboard_stats",
        summary="Get Dashboard Statistics",
        description=(
            "Aggregated statistics across all projects user has access to. "
            "Includes percentage changes compared to 7 days ago. "
            "Optimized with single query using annotations."
        ),
    )
    @action(detail=False, methods=["get"], url_path="dashboard-stats")
    def dashboard_stats(self, request):
        """Return dashboard statistics optimized with annotations."""
        user = request.user
        week_ago = timezone.now() - timedelta(days=7)

        projects = Project.objects.filter(
            workspace__members__user=user,
            workspace__members__is_active=True,
        ).distinct()

        current_stats = projects.aggregate(
            total_active_projects=Count(
                "id",
                filter=Q(status="active"),
                distinct=True,
            ),
            total_team_members=Count(
                "team_members",
                filter=Q(team_members__is_active=True),
                distinct=True,
            ),
            total_active_issues=Count(
                "issues",
                filter=Q(issues__is_active=True),
                distinct=True,
            ),
            total_projects=Count("id", distinct=True),
        )

        previous_stats = projects.aggregate(
            prev_projects=Count(
                "id",
                filter=Q(
                    status="active",
                    created_at__lte=week_ago,
                ),
                distinct=True,
            ),
            prev_members=Count(
                "team_members",
                filter=Q(
                    team_members__is_active=True,
                    team_members__joined_at__lte=week_ago,
                ),
                distinct=True,
            ),
            prev_issues=Count(
                "issues",
                filter=Q(
                    issues__is_active=True,
                    issues__created_at__lte=week_ago,
                ),
                distinct=True,
            ),
            prev_total_projects=Count(
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
                "total_issues": current_stats["total_active_issues"] or 0,
                "total_issues_change_pct": self._calc_pct(
                    current_stats["total_active_issues"],
                    previous_stats["prev_issues"],
                ),
                "total_projects": current_stats["total_projects"] or 0,
                "total_projects_change_pct": self._calc_pct(
                    current_stats["total_projects"],
                    previous_stats["prev_total_projects"],
                ),
            },
            status=status.HTTP_200_OK,
        )
